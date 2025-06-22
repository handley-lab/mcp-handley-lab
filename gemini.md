**Prompt Title:** Blueprint for a Greenfield API Rewrite

**Your Role:** You are an expert software architect specializing in API design and code modernization. You are tasked with analyzing a legacy codebase and the documentation for a modern Python SDK to create a detailed blueprint for a complete, from-scratch rewrite.

**The Context:** I have a codebase for a software framework. While the API functionality is sound, the underlying code has significant technical debt, largely because it was developed in a custom environment and then migrated to the Model Context Protocol (MCP) Python SDK. This has resulted in a codebase that is too complex and difficult to maintain.

**The Goal:** Your primary objective is to produce a comprehensive markdown report that I can hand directly to a skilled Python developer. This report will serve as the sole technical specification for rewriting the entire framework from scratch, leveraging the full capabilities of the modern MCP Python SDK. The new implementation must be clean, idiomatic, and uninfluenced by the legacy code's internal logic.

**Core Instructions:**

Analyze the provided legacy codebase and the Python SDK's README. Then, generate a single markdown report containing the following two sections. Use maximum effort and detail, with no restriction on output length.

---

# **Section 1: Logical API & Tool Specification**

**Objective:** Reverse-engineer and document the public-facing API contract of the legacy codebase. This section must capture **what** the API does, not **how** it is implemented. Do not include any source code from the legacy codebase.

**Required Components:**

1.  **High-Level Framework Purpose:**
    *   Begin with a concise summary of the framework's overall purpose and its primary function, as inferred from its collection of tools and their methods.

2.  **Complete Tool Inventory:**
    *   Provide a definitive list of all the core tools available within the framework.

3.  **Detailed Tool Schemas & Method Descriptions:**
    *   For each tool identified above, create a detailed breakdown. For each tool, you must:
        *   Extract the user-facing description of the tool's purpose (often found in schemas or docstrings).
        *   List all the public methods associated with that tool.
        *   For **each method**, provide the following details in a structured format:
            *   **Method Name:** The name of the function/method.
            *   **Description:** The user-facing text or comment that explains what the method does.
            *   **Input Parameters:** A list of all arguments or parameters the method accepts, including their names, expected data types (e.g., string, integer, boolean), and any descriptions of what they are for.
            *   **Return Value:** A description of what the method returns, including its data type and structure.

---

# **Section 2: Rewrite & Implementation Strategy using the Python SDK**

**Objective:** Provide a high-level strategic guide for a developer who is already skilled with the provided Python SDK. This strategy should guide them in building a new, clean implementation of the API specified in Section 1.

**Required Components:**

1.  **Architectural Recommendations:**
    *   Suggest a modern, clean, and scalable project and directory structure for the new Python project.
    *   Advise on how to logically group the tools and models within this new structure.

2.  **Mapping Legacy API to the Modern SDK:**
    *   Based on the provided SDK README, describe the recommended approach for implementing the API.
    *   For each tool and its methods (as documented in Section 1), suggest the most appropriate class, decorator, or function from the Python SDK to use for its implementation. For instance, "The legacy 'DataFetcher' tool should be implemented as a class inheriting from the SDK's `BaseTool`," or "The `@tool` decorator should be used for the following methods..."

3.  **Key Implementation Considerations for the Contractor:**
    *   Highlight important areas the developer should focus on, such as:
        *   **Configuration Management:** How should API keys, endpoints, and other settings be managed in a way that aligns with the SDK?
        *   **Error Handling:** What is the idiomatic way to handle and raise errors according to the SDK's design?
        *   **Data Modeling:** Recommend how to define data structures or classes for the complex objects that are passed into or returned from the API methods.

4.  **Suggested Development Roadmap:**
    *   Provide a high-level, logical sequence of steps for the developer to follow during the rewrite. This will help ensure the project is built in an orderly fashion. (e.g., 1. Set up the base project structure. 2. Implement the authentication tool first as it is a core dependency. 3. Implement the 'Tool A' and its methods. 4. Write unit tests for 'Tool A'..., etc.).

---

**Input Resources:**

=========== LEGACY CODEBASE ===========


Project Path: mcp_handley_lab

Source Tree:

```txt
mcp_handley_lab
├── __init__.py
├── code2prompt
│   ├── README.md
│   ├── requirements.txt
│   ├── schemas.yml
│   └── server.py
├── constants.py
├── google_calendar
│   ├── README.md
│   ├── requirements.txt
│   ├── server.py
│   └── server_legacy.py
├── jq
│   ├── README.md
│   ├── requirements.txt
│   ├── schemas.yml
│   └── server.py
├── llm
│   ├── __init__.py
│   ├── config.py
│   ├── gemini
│   │   ├── README.md
│   │   ├── requirements.txt
│   │   └── server.py
│   ├── openai
│   │   ├── README.md
│   │   ├── requirements.txt
│   │   └── server.py
│   ├── pricing.json
│   ├── requirements.txt
│   ├── schema_utils.py
│   ├── usage_tracker.py
│   └── utils.py
├── memory.py
├── server.py
├── tool_chainer
│   ├── README.md
│   ├── requirements.txt
│   ├── server.py
│   └── server_legacy.py
├── utils.py
└── vim
    ├── README.md
    ├── __init__.py
    ├── requirements.txt
    ├── schemas.yml
    ├── server.py
    └── test_server.py

```

`mcp_handley_lab/__init__.py`:

```py
"""
MCP (Model Context Protocol) Package
Contains all MCP servers and core protocol utilities
"""

from mcp_handley_lab.server import MCPServer, CLICommandServer, APIServer
from mcp_handley_lab.utils import setup_unbuffered_io

__version__ = "2.0.0a5"

__all__ = [
    'MCPServer', 
    'CLICommandServer',
    'APIServer',
    'setup_unbuffered_io'
]
```

`mcp_handley_lab/code2prompt/README.md`:

```md
# Code2Prompt MCP Server

MCP server that wraps the `code2prompt` CLI tool to generate structured prompts from codebases.

## Overview

The Code2Prompt MCP server provides access to the powerful `code2prompt` CLI tool through the Model Context Protocol. This allows Claude Code to generate structured representations of codebases that can be efficiently passed to other AI models for analysis.

## Prerequisites

- `code2prompt` CLI tool installed and available in PATH
- Python 3.8+

### Installing code2prompt

The code2prompt tool can be installed via:

```bash
# Using cargo (Rust)
cargo install code2prompt

# Or download from GitHub releases
# See: https://github.com/mufeedvh/code2prompt
```

## Available Tools

### `generate_prompt`
Generate a structured prompt from a codebase with full customization options.

**Key Features:**
- **File Output**: Generates files by default for efficient use with other AI models
- **Pattern Filtering**: Include/exclude files with glob patterns
- **Multiple Formats**: Markdown, JSON, or XML output
- **Source Options**: Line numbers, directory trees, absolute paths
- **Token Counting**: Built-in tokenization with multiple encoders

**Parameters:**
- `path` (required): Path to the codebase directory
- `output_file` (optional): Custom output file path (defaults to temporary file)
- `include`: Array of patterns to include (e.g., `["*.py", "*.js"]`)
- `exclude`: Array of patterns to exclude (e.g., `["node_modules", "*.log"]`)
- `output_format`: `"markdown"` (default), `"json"`, or `"xml"`
- `line_numbers`: Add line numbers to source code
- `full_directory_tree`: Include complete directory structure
- `follow_symlinks`: Follow symbolic links
- `hidden`: Include hidden files and directories
- `no_codeblock`: Disable markdown code block wrapping
- `absolute_paths`: Use absolute instead of relative paths
- `encoding`: Tokenizer (`"cl100k"`, `"p50k"`, `"p50k_edit"`, `"r50k"`, `"gpt2"`)
- `tokens`: Token count format (`"format"` or `"raw"`)
- `sort`: File sorting (`"name_asc"`, `"name_desc"`, `"date_asc"`, `"date_desc"`)

### `analyze_codebase`
Quick codebase analysis with directory tree and token counts only.

**Parameters:**
- `path` (required): Path to the codebase directory
- `include`: Array of include patterns
- `exclude`: Array of exclude patterns
- `hidden`: Include hidden files
- `encoding`: Tokenizer for token counting

### `git_diff`
Generate git diffs and branch comparisons.

**Parameters:**
- `path` (required): Path to the git repository
- `mode`: `"diff"` (working changes), `"branch_diff"`, or `"branch_log"`
- `branch1`, `branch2`: Required for branch comparisons
- `include`, `exclude`: Pattern filtering

## Usage Examples

```python
# Generate full codebase prompt
code2prompt:generate_prompt(
    path="/path/to/project",
    include=["*.py", "*.js"],
    exclude=["node_modules", "__pycache__"],
    line_numbers=True,
    output_format="markdown"
)

# Quick analysis
code2prompt:analyze_codebase(
    path="/path/to/project",
    exclude=["*.log", "tmp/"]
)

# Git diff
code2prompt:git_diff(
    path="/path/to/repo",
    mode="branch_diff",
    branch1="main",
    branch2="feature-branch"
)
```

## Integration with Other AI Models

The server outputs file paths by default, making it efficient to pass large codebases to other AI models:

```python
# Generate codebase file
result = code2prompt:generate_prompt(path="/my/project")
# Result contains file path like: /tmp/code2prompt_abc123.md

# Pass to Gemini for analysis
gemini:document_review(files=[{"path": "/tmp/code2prompt_abc123.md"}])
```

This approach avoids consuming Claude's context window with large codebases while enabling comprehensive AI analysis.

## Setup

1. **Install code2prompt CLI tool**
2. **Register with Claude Code:**
   ```bash
   claude config mcp add code2prompt --scope user --command "python /path/to/code2prompt/server.py"
   ```

## Error Handling

The server gracefully handles:
- Missing code2prompt CLI tool
- Invalid paths and parameters
- File system errors
- Git repository issues

Use the `server_info` tool to check status and troubleshoot issues.
```

`mcp_handley_lab/code2prompt/requirements.txt`:

```txt
# No additional Python dependencies required
# code2prompt CLI tool must be installed separately
```

`mcp_handley_lab/code2prompt/schemas.yml`:

```yml
tools:
  generate_prompt:
    name: generate_prompt
    description: Create a structured, token-counted summary of a codebase and save it to a file. Returns the output path for large-scale analysis.
    inputSchema:
      type: object
      properties:
        path:
          type: string
          description: The absolute or relative path to the codebase directory to be processed.
        output_file:
          type: string
          description: Optional output file path. If omitted, a temporary file is created.
        include:
          type: array
          items:
            type: string
          description: "Optional. An array of glob patterns (e.g., `['*.py', '*.js']`) to specify which files to include. If provided, only files matching these patterns will be processed."
          default: []
        exclude:
          type: array
          items:
            type: string
          description: "Optional. An array of glob patterns (e.g., `['node_modules', '*.log']`) to exclude files and directories. Exclusions take precedence over inclusions."
          default: []
        output_format:
          type: string
          enum: [markdown, json, xml]
          description: "Optional. The desired format for the output. 'markdown' is human-readable with code blocks; 'json' and 'xml' are machine-readable. Defaults to 'markdown'."
          default: markdown
        line_numbers:
          type: boolean
          description: Optional. If true, adds line numbers to the source code blocks within the output. Defaults to false.
          default: false
        full_directory_tree:
          type: boolean
          description: List the full directory tree
          default: false
        follow_symlinks:
          type: boolean
          description: Follow symlinks
          default: false
        hidden:
          type: boolean
          description: Include hidden directories and files
          default: false
        no_codeblock:
          type: boolean
          description: Disable wrapping code inside markdown code blocks
          default: false
        absolute_paths:
          type: boolean
          description: Use absolute paths instead of relative
          default: false
        encoding:
          type: string
          enum: [cl100k, p50k, p50k_edit, r50k, gpt2]
          description: Tokenizer to use for token count
          default: cl100k
        tokens:
          type: string
          enum: [raw, format]
          description: Display token count format
          default: format
        sort:
          type: string
          enum: [name_asc, name_desc, date_asc, date_desc]
          description: Sort order for files
          default: name_asc
      required: [path]
    annotations:
      title: Generate Codebase Prompt
      readOnlyHint: false
      destructiveHint: false
      idempotentHint: false
      openWorldHint: false

  analyze_codebase:
    name: analyze_codebase
    description: Analyze codebase structure and get directory tree with token counts
    inputSchema:
      type: object
      properties:
        path:
          type: string
          description: Path to the codebase directory
        include:
          type: array
          items:
            type: string
          description: Patterns to include
          default: []
        exclude:
          type: array
          items:
            type: string
          description: Patterns to exclude
          default: []
        hidden:
          type: boolean
          description: Include hidden directories and files
          default: false
        encoding:
          type: string
          enum: [cl100k, p50k, p50k_edit, r50k, gpt2]
          description: Tokenizer to use for token count
          default: cl100k
      required: [path]
    annotations:
      title: Analyze Codebase Structure
      readOnlyHint: true
      destructiveHint: false
      idempotentHint: false
      openWorldHint: false

  git_diff:
    name: git_diff
    description: Generate git diff or branch comparison using code2prompt
    inputSchema:
      type: object
      properties:
        path:
          type: string
          description: Path to the git repository
        mode:
          type: string
          enum: [diff, branch_diff, branch_log]
          description: Type of diff to generate
          default: diff
        branch1:
          type: string
          description: First branch (for branch comparisons)
        branch2:
          type: string
          description: Second branch (for branch comparisons)
        include:
          type: array
          items:
            type: string
          description: Patterns to include
          default: []
        exclude:
          type: array
          items:
            type: string
          description: Patterns to exclude
          default: []
      required: [path]
    annotations:
      title: Generate Git Diff Analysis
      readOnlyHint: true
      destructiveHint: false
      idempotentHint: false
      openWorldHint: false

  server_info:
    name: server_info
    description: Get Code2Prompt server status and error information
    inputSchema:
      type: object
      properties: {}
    annotations:
      title: Server Information
      readOnlyHint: true
      destructiveHint: false
      idempotentHint: true
      openWorldHint: false
```

`mcp_handley_lab/code2prompt/server.py`:

```py
#!/usr/bin/env python3
"""
FastMCP-based Code2prompt Server
Modern implementation using the official python-sdk
"""

import os
import subprocess
import shutil
import tempfile
import uuid
from typing import Dict, Any, List, Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic_settings import BaseSettings


class Code2PromptSettings(BaseSettings):
    """Settings for Code2prompt server"""
    cli_command: str = "code2prompt"
    
    class Config:
        env_prefix = "CODE2PROMPT_"


# Initialize settings and code2prompt availability at module level
settings = Code2PromptSettings()

# Check if code2prompt CLI is available
code2prompt_available = False
error_message = ""
cli_command = settings.cli_command

if shutil.which(settings.cli_command):
    code2prompt_available = True
    cli_command = settings.cli_command
    error_message = ""
else:
    code2prompt_available = False
    error_message = f"code2prompt CLI not found. Please install it first: pip install code2prompt"


# Create FastMCP app
mcp = FastMCP(
    "Code2Prompt MCP Server",
    instructions="Wraps the code2prompt CLI tool to generate structured prompts from codebases for AI analysis."
)


def run_code2prompt_command(args: List[str]) -> Dict[str, Any]:
    """Run code2prompt command and return result"""
    if not code2prompt_available:
        return {
            "success": False,
            "error": error_message,
            "output": "",
            "stderr": ""
        }
    
    try:
        cmd = [cli_command] + args
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )
        
        return {
            "success": result.returncode == 0,
            "output": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "command": " ".join(cmd)
        }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Command timed out after 5 minutes",
            "output": "",
            "stderr": ""
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "output": "",
            "stderr": ""
        }


@mcp.tool(
    name="generate_prompt",
    description="Generates a structured text representation of a codebase from a directory path. Returns the path to the generated output file.",
    annotations=ToolAnnotations(
        title="Generate Code2Prompt",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False
    )
)
def generate_prompt(
    path: str,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    output_file: Optional[str] = None,
    format: str = "markdown"
) -> str:
    """Generate structured prompt from codebase"""
    
    if not code2prompt_available:
        raise RuntimeError(f"Code2prompt not available: {error_message}")
    
    try:
        # Validate path
        if not os.path.exists(path):
            raise FileNotFoundError(f"Path does not exist: {path}")
        
        # Build command args
        args = [path]
        
        if include:
            for pattern in include:
                args.extend(["--include", pattern])
        
        if exclude:
            for pattern in exclude:
                args.extend(["--exclude", pattern])
        
        if format:
            args.extend(["--output-format", format])
        
        # Handle output file
        temp_file = None
        if output_file:
            args.extend(["--output-file", output_file])
        else:
            # Create temporary file
            temp_file = os.path.join(tempfile.gettempdir(), f"code2prompt_{uuid.uuid4().hex[:8]}.md")
            args.extend(["--output-file", temp_file])
            output_file = temp_file
        
        # Run command
        result = run_code2prompt_command(args)
        
        if not result["success"]:
            error_msg = result.get("error") or result.get("stderr") or "Unknown error"
            raise RuntimeError(f"Code2prompt command failed: {error_msg}")
        
        # Check if output file was created
        if not os.path.exists(output_file):
            raise IOError(f"Output file was not created: {output_file}")
        
        # Get file info
        file_size = os.path.getsize(output_file)
        
        success_msg = f"""✅ **Code2Prompt Generation Successful**

📁 **Output File Path:** `{output_file}`
📏 **File Size:** {file_size:,} bytes

💡 **Next Steps:** You can now use this file path (e.g., in a 'files' parameter) with other AI tools like Gemini or OpenAI for comprehensive analysis, without incurring direct context window usage from this response."""
        
        return success_msg
        
    except Exception as e:
        raise RuntimeError(f"An unexpected error occurred while generating the prompt: {e}")


@mcp.tool(
    name="analyze_codebase",
    description="Performs a quick analysis of a codebase directory, returning a text-based directory tree and token count.",
    annotations=ToolAnnotations(
        title="Analyze Codebase Structure",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False
    )
)
def analyze_codebase(
    path: str,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None
) -> str:
    """Quick analysis of codebase structure"""
    
    if not code2prompt_available:
        raise RuntimeError(f"Code2prompt not available: {error_message}")
    
    try:
        # Validate path
        if not os.path.exists(path):
            raise FileNotFoundError(f"Path does not exist: {path}")
        
        # Build command for structure analysis (use --full-directory-tree for structure)
        args = [path, "--full-directory-tree"]
        
        if include:
            for pattern in include:
                args.extend(["--include", pattern])
        
        if exclude:
            for pattern in exclude:
                args.extend(["--exclude", pattern])
        
        # Run command
        result = run_code2prompt_command(args)
        
        if not result["success"]:
            error_msg = result.get("error") or result.get("stderr") or "Unknown error"
            raise RuntimeError(f"Codebase analysis command failed: {error_msg}")
        
        output = result["output"].strip()
        if not output:
            raise ValueError("No analysis output was generated by code2prompt.")
        
        return f"📊 **Codebase Structure Analysis**\n\n{output}"
        
    except Exception as e:
        raise RuntimeError(f"An unexpected error occurred while analyzing the codebase: {e}")


@mcp.tool(
    name="git_diff",
    description="Generates a structured text representation of git changes (staged or between commits) from a local repository path. Returns the path to the generated output file.",
    annotations=ToolAnnotations(
        title="Git Diff to Prompt",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False
    )
)
def git_diff(
    path: str = ".",
    staged: bool = False,
    commit_range: Optional[str] = None,
    output_file: Optional[str] = None
) -> str:
    """Generate prompt from git diff"""
    
    if not code2prompt_available:
        raise RuntimeError(f"Code2prompt not available: {error_message}")
    
    try:
        # Validate path
        if not os.path.exists(path):
            raise FileNotFoundError(f"Path does not exist: {path}")
        
        # Build command args
        args = [path, "--diff"]
        
        if staged:
            args.append("--staged")
        
        if commit_range:
            args.extend(["--commit-range", commit_range])
        
        # Handle output file
        temp_file = None
        if output_file:
            args.extend(["--output-file", output_file])
        else:
            # Create temporary file
            temp_file = os.path.join(tempfile.gettempdir(), f"git_diff_{uuid.uuid4().hex[:8]}.md")
            args.extend(["--output-file", temp_file])
            output_file = temp_file
        
        # Run command
        result = run_code2prompt_command(args)
        
        if not result["success"]:
            error_msg = result.get("error") or result.get("stderr") or "Unknown error"
            raise RuntimeError(f"Git diff command failed: {error_msg}")
        
        # Check if output file was created
        if not os.path.exists(output_file):
            raise IOError(f"Output file was not created: {output_file}")
        
        # Get file info
        file_size = os.path.getsize(output_file)
        
        success_msg = f"""✅ **Git Diff Prompt Generated**

📁 **Output File Path:** `{output_file}`
📏 **File Size:** {file_size:,} bytes
🔄 **Type:** {'Staged changes' if staged else 'Working directory changes'}
{f'📝 **Range:** {commit_range}' if commit_range else ''}

💡 **Usage:** Use this file with AI tools to analyze code changes."""
        
        return success_msg
        
    except Exception as e:
        raise RuntimeError(f"An unexpected error occurred while generating the git diff: {e}")


@mcp.tool(
    name="server_info",
    description="Checks the status of the code2prompt server and verifies that the code2prompt CLI tool is installed and available.",
    annotations=ToolAnnotations(
        title="Code2Prompt Server Status",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False
    )
)
def server_info() -> str:
    """Get server status and configuration info"""
    if code2prompt_available:
        # Get version info
        version_result = run_code2prompt_command(["--version"])
        version_info = version_result.get("output", "Unknown").strip() if version_result["success"] else "Unknown"
        
        return f"""✅ **Code2Prompt Server Available**

🔧 **Configuration:**
- CLI Command: {cli_command}
- Version: {version_info}

🛠️ **Available Tools:**
- generate_prompt: Generate structured prompts from codebases
- analyze_codebase: Quick codebase structure analysis
- git_diff: Generate prompts from git changes
- server_info: This status information

💡 **Usage Tips:**
- Use include/exclude patterns to filter files
- Output files are created in temp directory if not specified
- Generated files can be used with AI tools for analysis
- Large codebases may take time to process

📖 **Documentation:** https://github.com/mufeedvh/code2prompt"""
    else:
        return f"""❌ **Code2Prompt Server Unavailable**

🔴 **Error:** {error_message}

🔧 **Setup Required:**
1. Install code2prompt: `pip install code2prompt`
2. Or install from source: `git clone https://github.com/mufeedvh/code2prompt && cd code2prompt && pip install .`
3. Restart the server

📚 **More Info:** https://github.com/mufeedvh/code2prompt"""


def main():
    """Main entry point"""
    # Run with stdio transport (synchronous)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
```

`mcp_handley_lab/constants.py`:

```py
"""
Centralized constants for MCP servers
Contains magic numbers, common strings, emojis, and configuration defaults
"""

# Version management
from mcp_handley_lab import __version__
MCP_VERSION = __version__

# Emojis for consistent messaging
EMOJI_ERROR = "❌"
EMOJI_SUCCESS = "✅"
EMOJI_INFO = "ℹ️"
EMOJI_ROBOT = "🤖"
EMOJI_WARNING = "⚠️"
EMOJI_CALENDAR = "📅"
EMOJI_CODE = "💻"

# Token estimation constants
IMAGE_ANALYSIS_TOKEN_ESTIMATE = 1000  # Rough estimate for image processing tokens
TOKEN_ESTIMATION_DIVISOR = 4  # Characters to tokens rough conversion
IMAGE_TOKENS_PER_IMAGE = 1000  # Base token count per image for cost estimation

# Default limits and timeouts
DEFAULT_MAX_RESULTS = 100
DEFAULT_DESCRIPTION_TRUNCATE_LENGTH = 100
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 4096

# API Key placeholders (for validation)
PLACEHOLDER_API_KEY = "YOUR_API_KEY_HERE"

# Common error message templates
MSG_SERVICE_NOT_AVAILABLE = "{emoji} **{service_name} Not Available**\n\nError: {error_message}"
MSG_UNKNOWN_TOOL = "{emoji} **Unknown Tool**\n\nError: Tool '{tool_name}' is not recognized."
MSG_TOOL_EXECUTION_FAILED = "{emoji} **Tool Execution Failed**\n\nError in '{tool_name}': {error_message}"
MSG_INVALID_ARGUMENTS = "{emoji} **Invalid Arguments**\n\nError: {error_message}"
MSG_FILE_NOT_FOUND = "{emoji} **File Not Found**\n\nError: {file_path}"
MSG_PERMISSION_DENIED = "{emoji} **Permission Denied**\n\nError: {error_message}"

# CLI tool error templates
MSG_CLI_COMMAND_FAILED = (
    "{emoji} **{tool_name} command failed**\n\n"
    "Command: {command}\n"
    "Error: {error}\n\n"
    "Please check that:\n"
    "- The path exists and is accessible\n"
    "- You have necessary permissions\n"
    "- The {tool_name} tool is properly installed"
)

MSG_CLI_EXECUTION_FAILED = (
    "{emoji} **Failed to execute {tool_name}**\n\n"
    "Error: {error}\n\n"
    "Please ensure {tool_name} is installed and accessible in your PATH."
)

MSG_CLI_UNEXPECTED_ERROR = "{emoji} **Unexpected error running {tool_name}**\n\nError: {error}"

# Success message templates
MSG_SUCCESS = "{emoji} **{operation} Successful**"
MSG_OPERATION_COMPLETE = "{emoji} **Operation Complete**\n\n{details}"

# Google Calendar specific constants
CALENDAR_MAX_SUMMARY_LENGTH = 1000
CALENDAR_MAX_DESCRIPTION_LENGTH = 8192
CALENDAR_DEFAULT_WORK_START_HOUR = 9
CALENDAR_DEFAULT_WORK_END_HOUR = 17

# Model name validation patterns
GEMINI_MODEL_PREFIX = "gemini"
OPENAI_MODEL_PREFIXES = ["gpt", "o1", "o3", "o4", "chatgpt", "dall-e"]

# File type constants
SUPPORTED_IMAGE_TYPES = ["png", "jpg", "jpeg", "gif", "webp"]
SUPPORTED_DOCUMENT_TYPES = ["txt", "md", "py", "js", "ts", "json", "yaml", "yml"]
```

`mcp_handley_lab/google_calendar/README.md`:

```md
# Google Calendar MCP Server (FastMCP)

Google Calendar integration for Claude Code via Model Context Protocol (MCP). Now using the modern FastMCP framework for improved performance and standards compliance.

## Features

- **List Events**: View calendar events within date ranges
- **Create Events**: Add new events with attendees, descriptions, and timezones
- **Update Events**: Modify existing event details
- **Delete Events**: Remove events from calendar
- **List Calendars**: View all accessible calendars
- **Find Free Time**: Discover available time slots for scheduling

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Google Cloud Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the Google Calendar API
4. Create OAuth2 credentials:
   - Go to Credentials → Create Credentials → OAuth client ID
   - Application type: Desktop application
   - Download the JSON file
5. Save credentials as `~/.google_calendar_credentials.json`

### 3. First Run Authentication

```bash
python server.py
```

On first run, you'll be redirected to browser for OAuth consent. The access token will be saved to `~/.google_calendar_token.json`.

### 4. Register with Claude Code

```bash
claude config mcp add google-calendar --scope user python /path/to/server.py
```

## Available Tools

### list_events
List calendar events within a date range.

**Parameters:**
- `calendar_id` (optional): Calendar name (e.g., 'Work', 'Personal') or ID. Defaults to "primary". Calendar names are preferred for ease of use.
- `start_date` (optional): Start date in YYYY-MM-DD format
- `end_date` (optional): End date in YYYY-MM-DD format  
- `max_results` (optional): Maximum events to return, defaults to 10

### create_event
Create a new calendar event.

**Parameters:**
- `summary` (required): Event title
- `start_datetime` (required): Start time (ISO format or YYYY-MM-DD for all-day)
- `end_datetime` (required): End time (ISO format or YYYY-MM-DD for all-day)
- `calendar_id` (optional): Target calendar name (e.g., 'Work') or ID, defaults to "primary"
- `description` (optional): Event description
- `timezone` (optional): Timezone, defaults to "UTC"
- `attendees` (optional): Array of email addresses

### update_event
Update an existing calendar event.

**Parameters:**
- `event_id` (required): Event ID to update
- `calendar_id` (optional): Calendar name or ID, defaults to "primary"
- `summary` (optional): New event title
- `description` (optional): New description
- `start_datetime` (optional): New start time
- `end_datetime` (optional): New end time

### delete_event
Delete a calendar event.

**Parameters:**
- `event_id` (required): Event ID to delete
- `calendar_id` (optional): Calendar name or ID, defaults to "primary"

### list_calendars
List all accessible calendars.

**Parameters:** None

### find_time
Find free time slots in calendar.

**Parameters:**
- `calendar_id` (optional): Calendar name or ID to check, defaults to "primary"
- `start_date` (optional): Search start date
- `end_date` (optional): Search end date
- `duration_minutes` (optional): Required slot duration, defaults to 60
- `work_hours_only` (optional): Limit to 9-17 hours, defaults to true

## Usage Examples

### List Today's Events
```json
{
  "name": "list_events",
  "arguments": {}
}
```

### List Events in Specific Calendar (using name)
```json
{
  "name": "list_events",
  "arguments": {
    "calendar_id": "Work",
    "start_date": "2024-01-15",
    "end_date": "2024-01-20"
  }
}
```

### Create Meeting in Specific Calendar
```json
{
  "name": "create_event",
  "arguments": {
    "calendar_id": "Work",
    "summary": "Team Standup",
    "start_datetime": "2024-01-15T09:00:00",
    "end_datetime": "2024-01-15T09:30:00",
    "description": "Daily team sync",
    "attendees": ["teammate@company.com"]
  }
}
```

### Find 2-hour Block Next Week
```json
{
  "name": "find_time",
  "arguments": {
    "start_date": "2024-01-22",
    "end_date": "2024-01-26",
    "duration_minutes": 120
  }
}
```

## Security Notes

- OAuth2 tokens are stored in `~/.google_calendar_token.json`
- Credentials file contains client secrets - keep secure
- Tokens auto-refresh when expired
- Remove token file to re-authenticate

## Troubleshooting

### Authentication Issues
- Ensure credentials file is properly placed
- Check OAuth2 consent screen configuration
- Verify Calendar API is enabled in Google Cloud Console

### Permission Errors
- Check calendar sharing settings
- Verify OAuth2 scopes include calendar access
- Confirm user has appropriate calendar permissions

### Server Info
Use the `server_info` tool to check connection status and diagnose issues.
```

`mcp_handley_lab/google_calendar/requirements.txt`:

```txt
google-auth>=2.23.0
google-auth-oauthlib>=1.0.0
google-auth-httplib2>=0.1.0
google-api-python-client>=2.100.0
mcp>=1.0.0
pydantic-settings>=2.0.0
```

`mcp_handley_lab/google_calendar/server.py`:

```py
#!/usr/bin/env python3
"""
FastMCP-based Google Calendar Server
Modern implementation using the official python-sdk
"""

import os
import sys
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic_settings import BaseSettings


class GoogleCalendarSettings(BaseSettings):
    """Settings for Google Calendar server"""
    test_mode: bool = False
    credentials_file: str = "~/.google_calendar_credentials.json"
    token_file: str = "~/.google_calendar_token.json"
    test_credentials_file: str = "~/.google_calendar_test_credentials.json"
    test_token_file: str = "~/.google_calendar_test_token.json"
    
    class Config:
        env_prefix = "GOOGLE_CALENDAR_"


# Initialize settings and Google Calendar API at module level
settings = GoogleCalendarSettings()

# Initialize Google Calendar state
service = None
available = False
error_message = ""

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    
    SCOPES = ['https://www.googleapis.com/auth/calendar']
    
    # Use test account credentials if in test mode
    if settings.test_mode:
        token_file = os.path.expanduser(settings.test_token_file)
        credentials_file = os.path.expanduser(settings.test_credentials_file)
    else:
        token_file = os.path.expanduser(settings.token_file)
        credentials_file = os.path.expanduser(settings.credentials_file)
    
    creds = None
    
    # Load existing token
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    
    # If no valid credentials, get them
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_file):
                available = False
                error_message = f"Google Calendar credentials not found at {credentials_file}. Please set up OAuth2 credentials."
            else:
                flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)
        
        # Save credentials for next run
        if creds:
            with open(token_file, 'w') as token:
                token.write(creds.to_json())
    
    if creds:
        service = build('calendar', 'v3', credentials=creds)
        available = True
        error_message = ""
        
except ImportError as e:
    available = False
    error_message = f"Missing required packages: {e}. Install with: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client"
except Exception as e:
    available = False
    error_message = f"Failed to initialize Google Calendar API: {e}"


# Create FastMCP app
mcp = FastMCP(
    "Google Calendar MCP Server",
    instructions="Provides comprehensive Google Calendar operations including events, calendars, attendees, and sharing management."
)


def _resolve_calendar_name_or_id(calendar_name_or_id: str) -> str:
    """Resolve calendar name to ID"""
    if not available:
        raise ConnectionError(f"Google Calendar not available: {error_message}")
    
    # If it looks like an email/ID, return as-is
    if '@' in calendar_name_or_id or calendar_name_or_id == 'primary':
        return calendar_name_or_id
    
    # Search calendars by name
    try:
        calendars = service.calendarList().list().execute()
        for calendar in calendars.get('items', []):
            if calendar.get('summary', '').lower() == calendar_name_or_id.lower():
                return calendar['id']
        
        # If not found, return as-is (might still be valid)
        return calendar_name_or_id
        
    except Exception:
        # If search fails, return as-is
        return calendar_name_or_id


def _validate_event_summary(event: Dict[str, Any], expected_summary: str) -> None:
    """Validate event summary for safety"""
    actual_summary = event.get('summary', '')
    if actual_summary != expected_summary:
        raise ValueError("Safety Check Failed: The event summary does not match the expected value.")


@mcp.tool(
    name="server_info", 
    description="Get Google Calendar server status and error information",
    annotations=ToolAnnotations(
        title="Google Calendar Server Status",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False
    )
)
def server_info() -> str:
    """Get server status information"""
    if available:
        return "✅ Google Calendar MCP Server v1.0.0 - Connected and ready!"
    else:
        return f"🔴 ERROR: Google Calendar MCP Server v1.0.0 - {error_message}"


@mcp.tool(
    name="list_events",
    description="List calendar events within a date range. Searches ALL calendars by default for comprehensive results.",
    annotations=ToolAnnotations(
        title="List Calendar Events",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True
    )
)
def list_events(
    calendar_id: str = "all",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    max_results: int = 100
) -> str:
    """List calendar events"""
    if not available:
        raise ConnectionError(f"Google Calendar not available: {error_message}")
    
    # Resolve calendar name to ID if not "all"
    if calendar_id != "all":
        calendar_id = _resolve_calendar_name_or_id(calendar_id)
    
    # Handle date range
    if not start_date:
        start_date = datetime.now().date().isoformat()
    
    if not end_date:
        start_dt = datetime.fromisoformat(start_date)
        end_dt = start_dt + timedelta(days=7)
        end_date = end_dt.date().isoformat()
    
    # Convert to RFC3339 format for API
    time_min = f"{start_date}T00:00:00Z"
    time_max = f"{end_date}T23:59:59Z"
    
    try:
        # If searching all calendars
        if calendar_id == "all":
            return _search_all_calendars(time_min, time_max, max_results, start_date, end_date)
        
        # Single calendar search
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        if not events:
            return f"📅 **No events found**\n\n🗓️ **Period:** {start_date} to {end_date}\n📋 **Calendar:** {calendar_id}"
        
        # Format events
        event_list = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            title = event.get('summary', '(No title)')
            event_id = event.get('id', '')
            
            event_list.append(f"• **{title}** - {start} (ID: {event_id})")
        
        events_text = '\n'.join(event_list)
        
        return f"""📅 **Calendar Events Found: {len(events)}**

🗓️ **Period:** {start_date} to {end_date}
📋 **Calendar:** {calendar_id}

**Events:**
{events_text}"""
        
    except Exception as e:
        raise RuntimeError(f"Failed to list events: {e}")


def _search_all_calendars(time_min: str, time_max: str, max_results: int, start_date: str, end_date: str) -> str:
    """Search all calendars for events"""
    try:
        # Get all calendars
        calendars = service.calendarList().list().execute()
        all_events = []
        
        for calendar in calendars.get('items', []):
            calendar_id = calendar['id']
            calendar_name = calendar.get('summary', calendar_id)
            
            try:
                events_result = service.events().list(
                    calendarId=calendar_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()
                
                events = events_result.get('items', [])
                for event in events:
                    event['_calendar_name'] = calendar_name
                    all_events.append(event)
                    
            except Exception:
                # Skip calendars that can't be accessed
                continue
        
        # Sort all events by start time
        all_events.sort(key=lambda e: e['start'].get('dateTime', e['start'].get('date')))
        
        if not all_events:
            return f"📅 **No events found**\n\n🗓️ **Period:** {start_date} to {end_date}\n📋 **Searched:** All calendars"
        
        # Format events
        event_list = []
        for event in all_events[:max_results]:
            start = event['start'].get('dateTime', event['start'].get('date'))
            title = event.get('summary', '(No title)')
            calendar_name = event.get('_calendar_name', 'Unknown')
            event_id = event.get('id', '')
            
            event_list.append(f"• **{title}** - {start} ({calendar_name}) (ID: {event_id})")
        
        events_text = '\n'.join(event_list)
        
        return f"""📅 **Calendar Events Found: {len(all_events)} (showing {len(event_list)})**

🗓️ **Period:** {start_date} to {end_date}
📋 **Searched:** All calendars

**Events:**
{events_text}"""
        
    except Exception as e:
        raise RuntimeError(f"Failed to search all calendars: {e}")


@mcp.tool(
    name="get_event",
    description="Get a single calendar event by ID",
    annotations=ToolAnnotations(
        title="Get Calendar Event",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False
    )
)
def get_event(
    event_id: str,
    calendar_id: str = "primary"
) -> str:
    """Get a single event by ID"""
    if not available:
        raise ConnectionError(f"Google Calendar not available: {error_message}")
    
    try:
        calendar_id = _resolve_calendar_name_or_id(calendar_id)
        
        event = service.events().get(
            calendarId=calendar_id,
            eventId=event_id
        ).execute()
        
        # Format event details
        title = event.get('summary', '(No title)')
        description = event.get('description', '(No description)')
        start = event['start'].get('dateTime', event['start'].get('date'))
        end = event['end'].get('dateTime', event['end'].get('date'))
        location = event.get('location', '(No location)')
        
        attendees = event.get('attendees', [])
        attendee_list = []
        for attendee in attendees:
            email = attendee.get('email', '')
            response = attendee.get('responseStatus', 'needsAction')
            attendee_list.append(f"• {email} ({response})")
        
        attendees_text = '\n'.join(attendee_list) if attendee_list else "(No attendees)"
        
        return f"""📅 **Event Details**

**Title:** {title}
**Start:** {start}
**End:** {end}
**Location:** {location}
**Calendar:** {calendar_id}
**Event ID:** {event_id}

**Description:**
{description}

**Attendees:**
{attendees_text}"""
        
    except Exception as e:
        raise RuntimeError(f"Failed to get event: {e}")


@mcp.tool(
    name="create_event",
    description="Create a new calendar event",
    annotations=ToolAnnotations(
        title="Create Calendar Event",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True
    )
)
def create_event(
    summary: str,
    start_datetime: str,
    end_datetime: str,
    description: Optional[str] = None,
    calendar_id: str = "primary",
    timezone: str = "UTC",
    attendees: Optional[List[str]] = None
) -> str:
    """Create a new calendar event"""
    if not available:
        raise ConnectionError(f"Google Calendar not available: {error_message}")
    
    try:
        calendar_id = _resolve_calendar_name_or_id(calendar_id)
        
        # Build event object
        event = {
            'summary': summary,
            'start': {
                'dateTime': start_datetime,
                'timeZone': timezone,
            },
            'end': {
                'dateTime': end_datetime,
                'timeZone': timezone,
            },
        }
        
        if description:
            event['description'] = description
        
        if attendees:
            event['attendees'] = [{'email': email} for email in attendees]
        
        # Create the event
        created_event = service.events().insert(
            calendarId=calendar_id,
            body=event
        ).execute()
        
        event_id = created_event['id']
        event_link = created_event.get('htmlLink', '')
        
        return f"""✅ **Event Created Successfully**

📅 **Title:** {summary}
🕐 **Start:** {start_datetime}
🕐 **End:** {end_datetime}
📋 **Calendar:** {calendar_id}
🔗 **Event ID:** {event_id}
{f'🌐 **Link:** {event_link}' if event_link else ''}

💡 **Event has been added to your calendar!**"""
        
    except Exception as e:
        raise RuntimeError(f"Failed to create event: {e}")


@mcp.tool(
    name="update_event",
    description="Update an existing calendar event",
    annotations=ToolAnnotations(
        title="Update Calendar Event",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True
    )
)
def update_event(
    event_summary: str,
    event_id: str,
    summary: Optional[str] = None,
    start_datetime: Optional[str] = None,
    end_datetime: Optional[str] = None,
    description: Optional[str] = None,
    calendar_id: str = "primary"
) -> str:
    """Update an existing calendar event"""
    if not available:
        raise ConnectionError(f"Google Calendar not available: {error_message}")
    
    try:
        calendar_id = _resolve_calendar_name_or_id(calendar_id)
        
        # Get the existing event for validation
        existing_event = service.events().get(
            calendarId=calendar_id,
            eventId=event_id
        ).execute()
        
        # Validate event summary for safety
        _validate_event_summary(existing_event, event_summary)
        
        # Build update object with only provided fields
        updates = {}
        if summary is not None:
            updates['summary'] = summary
        if start_datetime is not None:
            updates['start'] = {'dateTime': start_datetime}
        if end_datetime is not None:
            updates['end'] = {'dateTime': end_datetime}
        if description is not None:
            updates['description'] = description
        
        if not updates:
            raise ValueError("No updates provided")
        
        # Update the event
        updated_event = service.events().patch(
            calendarId=calendar_id,
            eventId=event_id,
            body=updates
        ).execute()
        
        return f"""✅ **Event Updated Successfully**

📅 **Event:** {event_summary}
🔗 **Event ID:** {event_id}
📋 **Calendar:** {calendar_id}

**Updates Applied:**
{f'• Title: {summary}' if summary else ''}
{f'• Start: {start_datetime}' if start_datetime else ''}
{f'• End: {end_datetime}' if end_datetime else ''}
{f'• Description: Updated' if description else ''}

💡 **Event has been updated successfully!**"""
        
    except Exception as e:
        raise RuntimeError(f"Failed to update event: {e}")


@mcp.tool(
    name="delete_event",
    description="Delete a calendar event",
    annotations=ToolAnnotations(
        title="Delete Calendar Event",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False
    )
)
def delete_event(
    event_summary: str,
    event_id: str,
    calendar_id: str = "primary"
) -> str:
    """Delete a calendar event"""
    if not available:
        raise ConnectionError(f"Google Calendar not available: {error_message}")
    
    try:
        calendar_id = _resolve_calendar_name_or_id(calendar_id)
        
        # Get the existing event for validation
        existing_event = service.events().get(
            calendarId=calendar_id,
            eventId=event_id
        ).execute()
        
        # Validate event summary for safety
        _validate_event_summary(existing_event, event_summary)
        
        # Delete the event
        service.events().delete(
            calendarId=calendar_id,
            eventId=event_id
        ).execute()
        
        return f"""✅ **Event Deleted Successfully**

📅 **Event:** {event_summary}
🔗 **Event ID:** {event_id}
📋 **Calendar:** {calendar_id}

💡 **Event has been permanently removed from your calendar.**"""
        
    except Exception as e:
        raise RuntimeError(f"Failed to delete event: {e}")


@mcp.tool(
    name="list_calendars",
    description="List available calendars with their IDs, colors, and access levels. RECOMMENDED: Run this first to understand the calendar structure before searching for specific events or setting colors.",
    annotations=ToolAnnotations(
        title="List Available Calendars",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False
    )
)
def list_calendars() -> str:
    """List available calendars"""
    if not available:
        raise ConnectionError(f"Google Calendar not available: {error_message}")
    
    try:
        calendars = service.calendarList().list().execute()
        calendar_items = calendars.get('items', [])
        
        if not calendar_items:
            return "📅 **No calendars found**"
        
        calendar_list = []
        for calendar in calendar_items:
            name = calendar.get('summary', '(No name)')
            calendar_id = calendar.get('id', '')
            access_role = calendar.get('accessRole', 'unknown')
            primary = " (PRIMARY)" if calendar.get('primary') else ""
            color = calendar.get('backgroundColor', '#FFFFFF')
            
            calendar_list.append(f"• **{name}**{primary}")
            calendar_list.append(f"  ID: {calendar_id}")
            calendar_list.append(f"  Access: {access_role}")
            calendar_list.append(f"  Color: {color}")
            calendar_list.append("")
        
        calendars_text = '\n'.join(calendar_list)
        
        return f"""📅 **Available Calendars: {len(calendar_items)}**

{calendars_text}

💡 **Usage Tips:**
• Use calendar names (e.g., 'Work', 'Personal') or IDs in other commands
• PRIMARY calendar is your main Google Calendar
• Access levels: owner, reader, writer, freeBusyReader"""
        
    except Exception as e:
        raise RuntimeError(f"Failed to list calendars: {e}")


def main():
    """Main entry point"""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
```

`mcp_handley_lab/google_calendar/server_legacy.py`:

```py
#!/usr/bin/env python3
"""
Google Calendar MCP Server - Calendar operations via Google Calendar API
"""

import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json
import yaml

from mcp_handley_lab.server import APIServer
from mcp_handley_lab.utils import setup_unbuffered_io
from mcp_handley_lab.constants import (
    MCP_VERSION, EMOJI_ERROR, EMOJI_SUCCESS, EMOJI_CALENDAR,
    MSG_SERVICE_NOT_AVAILABLE, MSG_UNKNOWN_TOOL, MSG_INVALID_ARGUMENTS,
    DEFAULT_MAX_RESULTS, CALENDAR_MAX_SUMMARY_LENGTH, CALENDAR_MAX_DESCRIPTION_LENGTH,
    CALENDAR_DEFAULT_WORK_START_HOUR, CALENDAR_DEFAULT_WORK_END_HOUR
)

setup_unbuffered_io()

class GoogleCalendarServer(APIServer):
    def __init__(self):
        super().__init__("google-calendar-mcp", MCP_VERSION, "Google Calendar")
        self.service = None
        self._load_tool_schemas()
        self._setup_dispatch_table()
        self._initialize_service()
    
    def _initialize_service(self):
        """Initialize Google Calendar API service"""
        self._initialize_calendar_service()
    
    def _validate_event_summary(self, event: Dict[str, Any], expected_summary: str) -> Optional[str]:
        """Validate event summary for safety. Returns error message if validation fails, None if passes."""
        actual_summary = event.get('summary', '')
        if actual_summary != expected_summary:
            raise ValueError("Safety Check Failed: The event summary does not match the expected value.")
        return None

    def _load_tool_schemas(self):
        """Load tool schemas from YAML file"""
        schema_file = os.path.join(os.path.dirname(__file__), 'schemas.yml')
        self.load_tool_schemas(schema_file)

    def _setup_dispatch_table(self):
        """Setup tool dispatch table"""
        self.tool_handlers = {
            "server_info": self._handle_server_info,
            "list_events": self._handle_list_events,
            "get_event": self._handle_get_event,
            "create_event": self._handle_create_event,
            "update_event": self._handle_update_event,
            "delete_event": self._handle_delete_event,
            "list_calendars": self._handle_list_calendars,
            "move_event": self._handle_move_event,
            "copy_event": self._handle_copy_event,
            "patch_event": self._handle_patch_event,
            "instances": self._handle_instances,
            "quick_add": self._handle_quick_add,
            "watch_events": self._handle_watch_events,
            "create_calendar": self._handle_create_calendar,
            "update_calendar_color": self._handle_update_calendar_color,
            "find_time": self._handle_find_time,
            "get_calendar": self._handle_get_calendar,
            "delete_calendar": self._handle_delete_calendar,
            "patch_calendar": self._handle_patch_calendar,
            "add_attendees": self._handle_add_attendees,
            "manage_attendee_responses": self._handle_manage_attendee_responses,
            "send_invitations": self._handle_send_invitations,
            "list_acl_rules": self._handle_list_acl_rules,
            "insert_acl_rule": self._handle_insert_acl_rule,
            "update_acl_rule": self._handle_update_acl_rule,
            "delete_acl_rule": self._handle_delete_acl_rule,
            "add_reminders": self._handle_add_reminders,
            "add_conference_data": self._handle_add_conference_data,
        }

    def _initialize_calendar_service(self):
        """Initialize Google Calendar API service"""
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
            
            SCOPES = ['https://www.googleapis.com/auth/calendar']
            
            creds = None
            # Use test account credentials if in test mode
            if os.environ.get('GOOGLE_CALENDAR_TEST_MODE'):
                token_file = os.path.expanduser('~/.google_calendar_test_token.json')
                credentials_file = os.path.expanduser('~/.google_calendar_test_credentials.json')
            else:
                token_file = os.path.expanduser('~/.google_calendar_token.json')
                credentials_file = os.path.expanduser('~/.google_calendar_credentials.json')
            
            # Load existing token
            if os.path.exists(token_file):
                creds = Credentials.from_authorized_user_file(token_file, SCOPES)
            
            # If no valid credentials, get them
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if not os.path.exists(credentials_file):
                        self.error_message = f"Google Calendar credentials not found at {credentials_file}. Please set up OAuth2 credentials."
                        return
                    
                    flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
                    creds = flow.run_local_server(port=0)
                
                # Save credentials for next run
                with open(token_file, 'w') as token:
                    token.write(creds.to_json())
            
            self.service = build('calendar', 'v3', credentials=creds)
            self.available = True
            
        except ImportError as e:
            self.error_message = f"Missing required packages: {e}. Install with: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client"
        except Exception as e:
            self.error_message = f"Failed to initialize Google Calendar API: {e}"
    
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Return list of available tools"""
        if not self.available:
            return [self.tool_schemas.get('server_info', {})]
        
        # Return all available tools from schema
        available_tools = [
            'server_info', 'list_events', 'get_event', 'create_event', 
            'update_event', 'delete_event', 'list_calendars', 'move_event',
            'copy_event', 'patch_event', 'instances', 'quick_add', 'watch_events',
            'create_calendar', 'update_calendar_color', 'find_time', 'get_calendar',
            'delete_calendar', 'patch_calendar', 'add_attendees', 'manage_attendee_responses',
            'send_invitations', 'list_acl_rules', 'insert_acl_rule', 'update_acl_rule',
            'delete_acl_rule', 'add_reminders', 'add_conference_data'
        ]
        
        return [self.tool_schemas.get(tool, {}) for tool in available_tools if tool in self.tool_schemas]
    
    def handle_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Handle tool execution"""
        if not self.available:
            raise ConnectionError(f"Google Calendar not available: {self.error_message}")
        
        handler = self.tool_handlers.get(tool_name)
        if not handler:
            raise ValueError(f"Unknown tool: '{tool_name}' is not recognized.")
        
        try:
            # server_info takes no arguments
            if tool_name == "server_info":
                return handler()
            return handler(arguments)
        except Exception as e:
            raise RuntimeError(f"Tool execution failed in '{tool_name}': {e}")
    
    def _handle_server_info(self) -> str:
        """Handle server info request"""
        if self.available:
            return f"✅ Google Calendar MCP Server v1.0.0 - Connected and ready!"
        else:
            return f"🔴 ERROR: Google Calendar MCP Server v1.0.0 - {self.error_message}"
    
    def _handle_list_events(self, arguments: Dict[str, Any]) -> str:
        """List calendar events"""
        calendar_id = arguments.get("calendar_id", "all")
        max_results = arguments.get("max_results", DEFAULT_MAX_RESULTS)
        
        # Resolve calendar name to ID if not "all"
        if calendar_id != "all":
            calendar_id = self._resolve_calendar_name_or_id(calendar_id)
        
        # Handle date range
        start_date = arguments.get("start_date")
        if not start_date:
            start_date = datetime.now().date().isoformat()
        
        end_date = arguments.get("end_date")
        if not end_date:
            start_dt = datetime.fromisoformat(start_date)
            end_dt = start_dt + timedelta(days=7)
            end_date = end_dt.date().isoformat()
        
        # Convert to RFC3339 format for API
        time_min = f"{start_date}T00:00:00Z"
        time_max = f"{end_date}T23:59:59Z"
        
        # If searching all calendars
        if calendar_id == "all":
            return self._search_all_calendars(time_min, time_max, max_results, start_date, end_date)
        
        # Single calendar search
        events_result = self.service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        if not events:
            return f"No events found in calendar '{calendar_id}' from {start_date} to {end_date}"
        
        result = f"📅 **Calendar Events ({len(events)} found)**\n\n"
        
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            summary = event.get('summary', 'No title')
            event_id = event['id']
            
            # Format datetime
            if 'T' in start:  # DateTime event
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                time_str = f"{start_dt.strftime('%Y-%m-%d %H:%M')} - {end_dt.strftime('%H:%M')}"
            else:  # All-day event
                time_str = f"{start} (All day)"
            
            result += f"• **{summary}**\n"
            result += f"  - Time: {time_str}\n"
            result += f"  - ID: `{event_id}`\n"
            
            if event.get('description'):
                desc = event['description'][:100] + "..." if len(event['description']) > 100 else event['description']
                result += f"  - Description: {desc}\n"
            
            result += "\n"
        
        return result
    
    def _search_all_calendars(self, time_min: str, time_max: str, max_results: int, start_date: str, end_date: str) -> str:
        """Search all calendars for events"""
        # Get all calendars
        calendars_result = self.service.calendarList().list().execute()
        calendars = calendars_result.get('items', [])
        
        all_events = []
        calendar_names = {}
        
        # Search each calendar
        for calendar in calendars:
            cal_id = calendar['id']
            cal_name = calendar.get('summary', 'Unknown')
            calendar_names[cal_id] = cal_name
            
            try:
                events_result = self.service.events().list(
                    calendarId=cal_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()
                
                events = events_result.get('items', [])
                for event in events:
                    event['_calendar_id'] = cal_id
                    event['_calendar_name'] = cal_name
                    all_events.append(event)
            except Exception:
                # Skip calendars that can't be accessed
                continue
        
        if not all_events:
            return f"No events found across all calendars from {start_date} to {end_date}"
        
        # Sort all events by start time
        def get_event_start_time(event):
            start = event['start'].get('dateTime', event['start'].get('date'))
            if 'T' in start:
                return datetime.fromisoformat(start.replace('Z', '+00:00')).replace(tzinfo=None)
            else:
                return datetime.fromisoformat(f"{start}T00:00:00")
        
        all_events.sort(key=get_event_start_time)
        
        # Limit results
        if len(all_events) > max_results:
            all_events = all_events[:max_results]
        
        result = f"📅 **Calendar Events ({len(all_events)} found across all calendars)**\n\n"
        
        for event in all_events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            summary = event.get('summary', 'No title')
            event_id = event['id']
            calendar_name = event['_calendar_name']
            
            # Format datetime
            if 'T' in start:  # DateTime event
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                time_str = f"{start_dt.strftime('%Y-%m-%d %H:%M')} - {end_dt.strftime('%H:%M')}"
            else:  # All-day event
                time_str = f"{start} (All day)"
            
            result += f"• **{summary}**\n"
            result += f"  - Time: {time_str}\n"
            result += f"  - Calendar: {calendar_name}\n"
            result += f"  - ID: `{event_id}`\n"
            
            if event.get('description'):
                desc = event['description'][:100] + "..." if len(event['description']) > 100 else event['description']
                result += f"  - Description: {desc}\n"
            
            result += "\n"
        
        return result
    
    def _resolve_calendar_name_or_id(self, calendar_name_or_id: str) -> str:
        """Resolve calendar name or ID to calendar ID"""
        return self._resolve_calendar_name_or_id_safe(calendar_name_or_id) or calendar_name_or_id
    
    def _resolve_calendar_name_or_id_safe(self, calendar_name_or_id: str) -> Optional[str]:
        """Resolve calendar name to ID, or return ID if already an ID"""
        # Special case for "primary" which is a valid calendar reference
        if calendar_name_or_id.lower() == "primary":
            return "primary"
        
        # If it looks like an ID (contains @), return as-is
        if '@' in calendar_name_or_id:
            return calendar_name_or_id
        
        # Get all calendars and find by name
        calendars_result = self.service.calendarList().list().execute()
        calendars = calendars_result.get('items', [])
        
        matches = []
        for calendar in calendars:
            cal_name = calendar.get('summary', '')
            cal_id = calendar['id']
            
            # Exact match (case-insensitive)
            if cal_name.lower() == calendar_name_or_id.lower():
                return cal_id
            
            # Partial match for fuzzy matching
            if calendar_name_or_id.lower() in cal_name.lower():
                matches.append((cal_name, cal_id))
        
        # If no exact match but one partial match, use it
        if len(matches) == 1:
            return matches[0][1]
        
        # Multiple matches or no matches
        if len(matches) > 1:
            match_list = "\n".join([f"- {name}" for name, _ in matches])
            # Return the first match but warn about ambiguity
            return matches[0][1]
        
        # No matches - return None to let calling function handle the error gracefully
        return None
    
    def _get_master_event_id(self, event_id: str) -> str:
        """Extract master event ID from instance ID for recurring events (fallback method)"""
        # Instance IDs have format: masterID_RYYYYMMDDTHHMMSSZ
        if '_R' in event_id and 'T' in event_id:
            return event_id.split('_R')[0]
        
        # Also handle other recurring patterns like _YYYYMMDDTHHMMSSZ
        if '_' in event_id and len(event_id.split('_')[-1]) >= 15:  # Date suffix length
            return event_id.rsplit('_', 1)[0]
        
        # Already a master ID
        return event_id
    
    def _resolve_to_master_event_id(self, calendar_id: str, event_id: str) -> str:
        """Get master event ID by querying the API"""
        try:
            event = self.service.events().get(calendarId=calendar_id, eventId=event_id).execute()
            
            # If this is a recurring instance, get the master
            if 'recurringEventId' in event:
                return event['recurringEventId']
            
            # This is already a master event
            return event_id
        except Exception:
            # Fallback to string parsing
            return self._get_master_event_id(event_id)
    
    def _handle_create_event(self, arguments: Dict[str, Any]) -> str:
        """Create a new calendar event"""
        calendar_id = arguments.get("calendar_id", "primary")
        # Resolve calendar name to ID
        calendar_id = self._resolve_calendar_name_or_id(calendar_id)
        summary = arguments["summary"]
        description = arguments.get("description", "")
        start_datetime = arguments["start_datetime"]
        end_datetime = arguments["end_datetime"]
        timezone = arguments.get("timezone", "UTC")
        attendees = arguments.get("attendees", [])
        
        # Build event object
        event = {
            'summary': summary,
            'description': description,
        }
        
        # Handle all-day vs timed events
        if 'T' in start_datetime:
            # Timed event
            event['start'] = {
                'dateTime': start_datetime,
                'timeZone': timezone,
            }
            event['end'] = {
                'dateTime': end_datetime,
                'timeZone': timezone,
            }
        else:
            # All-day event
            event['start'] = {'date': start_datetime}
            event['end'] = {'date': end_datetime}
        
        # Add attendees if provided
        if attendees:
            event['attendees'] = [{'email': email} for email in attendees]
        
        # Create the event
        created_event = self.service.events().insert(calendarId=calendar_id, body=event).execute()
        
        return f"✅ **Event Created Successfully**\n\n" \
               f"• **Title:** {summary}\n" \
               f"• **Event ID:** `{created_event['id']}`\n" \
               f"• **Calendar:** {calendar_id}\n" \
               f"• **Link:** {created_event.get('htmlLink', 'N/A')}"
    
    def _handle_update_event(self, arguments: Dict[str, Any]) -> str:
        """Update an existing calendar event"""
        calendar_id = arguments.get("calendar_id", "primary")
        # Resolve calendar name to ID
        calendar_id = self._resolve_calendar_name_or_id(calendar_id)
        event_id = arguments["event_id"]
        
        # Get existing event
        event = self.service.events().get(calendarId=calendar_id, eventId=event_id).execute()
        
        # Validate event summary for safety
        error_msg = self._validate_event_summary(event, arguments["event_summary"])
        if error_msg:
            return error_msg
        
        # Update fields if provided
        if "summary" in arguments:
            event['summary'] = arguments["summary"]
        if "description" in arguments:
            event['description'] = arguments["description"]
        if "start_datetime" in arguments:
            if 'T' in arguments["start_datetime"]:
                event['start'] = {
                    'dateTime': arguments["start_datetime"],
                    'timeZone': event['start'].get('timeZone', 'UTC')
                }
            else:
                event['start'] = {'date': arguments["start_datetime"]}
        if "end_datetime" in arguments:
            if 'T' in arguments["end_datetime"]:
                event['end'] = {
                    'dateTime': arguments["end_datetime"],
                    'timeZone': event['end'].get('timeZone', 'UTC')
                }
            else:
                event['end'] = {'date': arguments["end_datetime"]}
        
        # Update the event
        updated_event = self.service.events().update(calendarId=calendar_id, eventId=event_id, body=event).execute()
        
        return f"✅ **Event Updated Successfully**\n\n" \
               f"• **Title:** {updated_event.get('summary', 'N/A')}\n" \
               f"• **Event ID:** `{event_id}`\n" \
               f"• **Link:** {updated_event.get('htmlLink', 'N/A')}"
    
    def _handle_move_event(self, arguments: Dict[str, Any]) -> str:
        """Move an event from one calendar to another (with smart recurring event handling)"""
        source_calendar = arguments["source_calendar"]
        target_calendar = arguments["target_calendar"]
        event_id = arguments["event_id"]
        
        try:
            # Resolve calendar names to IDs
            source_calendar_id = self._resolve_calendar_name_or_id(source_calendar)
            target_calendar_id = self._resolve_calendar_name_or_id(target_calendar)
            
            # Get the event from source calendar for event title
            event = self.service.events().get(calendarId=source_calendar_id, eventId=event_id).execute()
            event_title = event.get('summary', 'Untitled Event')
            is_recurring_instance = 'recurringEventId' in event
            
            # Try to move with original ID first
            try:
                moved_event = self.service.events().move(
                    calendarId=source_calendar_id,
                    eventId=event_id,
                    destination=target_calendar_id
                ).execute()
                
                event_type = " (recurring series)" if is_recurring_instance else ""
                return f"✅ **Event Moved Successfully**{event_type}\n\n" \
                       f"• **Event:** {event_title}\n" \
                       f"• **From:** {source_calendar}\n" \
                       f"• **To:** {target_calendar}\n" \
                       f"• **New Event ID:** `{moved_event['id']}`"
            
            except Exception as move_error:
                # Check if this is the recurring instance error
                if "Cannot change the organizer of an instance" in str(move_error):
                    # Auto-retry with master event ID
                    master_id = self._resolve_to_master_event_id(source_calendar_id, event_id)
                    
                    moved_event = self.service.events().move(
                        calendarId=source_calendar_id,
                        eventId=master_id,
                        destination=target_calendar_id
                    ).execute()
                    
                    return f"✅ **Recurring Event Series Moved Successfully**\n\n" \
                           f"• **Event:** {event_title}\n" \
                           f"• **From:** {source_calendar}\n" \
                           f"• **To:** {target_calendar}\n" \
                           f"• **Master Event ID:** `{moved_event['id']}`\n" \
                           f"• **Note:** Moved entire recurring series"
                else:
                    raise RuntimeError(f"Failed to move event: {move_error}")
        
        except Exception as e:
            raise RuntimeError(f"Failed to move event: {e}")
    
    def _handle_delete_event(self, arguments: Dict[str, Any]) -> str:
        """Delete a calendar event"""
        calendar_id = arguments.get("calendar_id", "primary")
        # Resolve calendar name to ID
        calendar_id = self._resolve_calendar_name_or_id(calendar_id)
        event_id = arguments["event_id"]
        
        # Get event details before deletion for confirmation
        try:
            event = self.service.events().get(calendarId=calendar_id, eventId=event_id).execute()
            event_title = event.get('summary', 'Untitled Event')
        except:
            event_title = "Unknown Event"
        
        # Validate event summary for safety
        error_msg = self._validate_event_summary(event, arguments["event_summary"])
        if error_msg:
            return error_msg
        
        # Delete the event
        self.service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        
        return f"✅ **Event Deleted Successfully**\n\n" \
               f"• **Deleted:** {event_title}\n" \
               f"• **Event ID:** `{event_id}`"
    
    def _handle_get_event(self, arguments: Dict[str, Any]) -> str:
        """Get a single calendar event by ID"""
        calendar_id = arguments.get("calendar_id", "primary")
        calendar_id = self._resolve_calendar_name_or_id(calendar_id)
        event_id = arguments["event_id"]
        
        try:
            event = self.service.events().get(calendarId=calendar_id, eventId=event_id).execute()
            
            # Format event details
            summary = event.get('summary', 'Untitled Event')
            description = event.get('description', '')
            location = event.get('location', '')
            
            # Handle datetime formatting
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            
            if 'T' in start:
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                time_str = f"{start_dt.strftime('%Y-%m-%d %H:%M')} - {end_dt.strftime('%H:%M')}"
            else:
                time_str = f"{start} (All day)"
            
            result = f"📅 **Event Details**\n\n"
            result += f"• **Title:** {summary}\n"
            result += f"• **Time:** {time_str}\n"
            if description:
                result += f"• **Description:** {description}\n"
            if location:
                result += f"• **Location:** {location}\n"
            result += f"• **Event ID:** `{event_id}`\n"
            result += f"• **Calendar ID:** `{calendar_id}`"
            
            return result
            
        except Exception as e:
            raise RuntimeError(f"Failed to get event: {e}")
    
    def _handle_copy_event(self, arguments: Dict[str, Any]) -> str:
        """Copy an event to a calendar"""
        calendar_id = arguments.get("calendar_id", "primary")
        calendar_id = self._resolve_calendar_name_or_id(calendar_id)
        event_data = arguments["event_data"]
        
        try:
            # Remove fields that shouldn't be copied
            clean_event_data = event_data.copy()
            fields_to_remove = ['id', 'iCalUID', 'etag', 'kind', 'created', 'updated', 
                              'creator', 'organizer', 'htmlLink', 'sequence']
            for field in fields_to_remove:
                clean_event_data.pop(field, None)
            
            # Import the event
            imported_event = self.service.events().import_(
                calendarId=calendar_id,
                body=clean_event_data
            ).execute()
            
            summary = imported_event.get('summary', 'Untitled Event')
            new_event_id = imported_event['id']
            
            return f"✅ **Event Copied Successfully**\n\n" \
                   f"• **Event:** {summary}\n" \
                   f"• **New Event ID:** `{new_event_id}`\n" \
                   f"• **Calendar:** {calendar_id}"
            
        except Exception as e:
            raise RuntimeError(f"Failed to copy event: {e}")
    
    def _handle_patch_event(self, arguments: Dict[str, Any]) -> str:
        """Partially update an existing calendar event"""
        calendar_id = arguments.get("calendar_id", "primary")
        calendar_id = self._resolve_calendar_name_or_id(calendar_id)
        event_id = arguments["event_id"]
        
        # Get existing event for validation
        event = self.service.events().get(calendarId=calendar_id, eventId=event_id).execute()
        
        # Validate event summary for safety
        error_msg = self._validate_event_summary(event, arguments["event_summary"])
        if error_msg:
            return error_msg
        
        # Build patch data from provided arguments
        patch_data = {}
        if "summary" in arguments:
            patch_data["summary"] = arguments["summary"]
        if "description" in arguments:
            patch_data["description"] = arguments["description"]
        if "start_datetime" in arguments:
            start_datetime = arguments["start_datetime"]
            timezone = arguments.get("timezone", "UTC")
            if 'T' in start_datetime:
                patch_data["start"] = {"dateTime": start_datetime, "timeZone": timezone}
            else:
                patch_data["start"] = {"date": start_datetime}
        if "end_datetime" in arguments:
            end_datetime = arguments["end_datetime"]
            timezone = arguments.get("timezone", "UTC")
            if 'T' in end_datetime:
                patch_data["end"] = {"dateTime": end_datetime, "timeZone": timezone}
            else:
                patch_data["end"] = {"date": end_datetime}
        
        try:
            updated_event = self.service.events().patch(
                calendarId=calendar_id,
                eventId=event_id,
                body=patch_data
            ).execute()
            
            summary = updated_event.get('summary', 'Untitled Event')
            
            return f"✅ **Event Updated Successfully**\n\n" \
                   f"• **Event:** {summary}\n" \
                   f"• **Event ID:** `{event_id}`\n" \
                   f"• **Updated Fields:** {list(patch_data.keys())}"
            
        except Exception as e:
            raise RuntimeError(f"Failed to update event: {e}")
    
    def _handle_instances(self, arguments: Dict[str, Any]) -> str:
        """Get instances of a recurring event"""
        calendar_id = arguments.get("calendar_id", "primary")
        calendar_id = self._resolve_calendar_name_or_id(calendar_id)
        event_id = arguments["event_id"]
        time_min = arguments.get("time_min")
        time_max = arguments.get("time_max")
        
        try:
            # Build request parameters
            params = {"calendarId": calendar_id, "eventId": event_id}
            if time_min:
                params["timeMin"] = time_min
            if time_max:
                params["timeMax"] = time_max
            
            instances_result = self.service.events().instances(**params).execute()
            instances = instances_result.get('items', [])
            
            if not instances:
                return f"No instances found for recurring event `{event_id}`"
            
            result = f"🔄 **Recurring Event Instances ({len(instances)} found)**\n\n"
            
            for instance in instances:
                summary = instance.get('summary', 'Untitled Event')
                start = instance['start'].get('dateTime', instance['start'].get('date'))
                end = instance['end'].get('dateTime', instance['end'].get('date'))
                instance_id = instance['id']
                
                if 'T' in start:
                    start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                    time_str = f"{start_dt.strftime('%Y-%m-%d %H:%M')} - {end_dt.strftime('%H:%M')}"
                else:
                    time_str = f"{start} (All day)"
                
                result += f"• **{summary}**\n"
                result += f"  - Time: {time_str}\n"
                result += f"  - Instance ID: `{instance_id}`\n\n"
            
            return result
            
        except Exception as e:
            raise RuntimeError(f"Failed to get event instances: {e}")
    
    def _handle_quick_add(self, arguments: Dict[str, Any]) -> str:
        """Create an event from a simple text string"""
        calendar_id = arguments.get("calendar_id", "primary")
        calendar_id = self._resolve_calendar_name_or_id(calendar_id)
        text = arguments["text"]
        
        try:
            created_event = self.service.events().quickAdd(
                calendarId=calendar_id,
                text=text
            ).execute()
            
            summary = created_event.get('summary', 'Untitled Event')
            event_id = created_event['id']
            
            # Format start time if available
            start = created_event['start'].get('dateTime', created_event['start'].get('date'))
            if 'T' in start:
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                time_str = start_dt.strftime('%Y-%m-%d %H:%M')
            else:
                time_str = start
            
            return f"✅ **Event Created from Text**\n\n" \
                   f"• **Event:** {summary}\n" \
                   f"• **Time:** {time_str}\n" \
                   f"• **Event ID:** `{event_id}`\n" \
                   f"• **Original Text:** {text}"
            
        except Exception as e:
            raise RuntimeError(f"Failed to create event from text: {e}")
    
    def _handle_watch_events(self, arguments: Dict[str, Any]) -> str:
        """Watch for changes to events in a calendar"""
        calendar_id = arguments.get("calendar_id", "primary")
        calendar_id = self._resolve_calendar_name_or_id(calendar_id)
        channel_id = arguments["channel_id"]
        webhook_url = arguments["webhook_url"]
        ttl = arguments.get("ttl", 3600)
        
        try:
            # Calculate expiration time
            import time
            expiration = int((time.time() + ttl) * 1000)  # Convert to milliseconds
            
            # Create watch request
            watch_request = {
                "id": channel_id,
                "type": "web_hook",
                "address": webhook_url,
                "expiration": str(expiration)
            }
            
            channel = self.service.events().watch(
                calendarId=calendar_id,
                body=watch_request
            ).execute()
            
            return f"✅ **Watch Channel Created**\n\n" \
                   f"• **Channel ID:** `{channel_id}`\n" \
                   f"• **Calendar:** {calendar_id}\n" \
                   f"• **Webhook URL:** {webhook_url}\n" \
                   f"• **Expires:** {ttl} seconds\n" \
                   f"• **Resource ID:** `{channel.get('resourceId', 'N/A')}`"
            
        except Exception as e:
            raise RuntimeError(f"Failed to create watch channel: {e}")
    
    def _handle_list_calendars(self, arguments: Dict[str, Any]) -> str:
        """List available calendars"""
        calendars_result = self.service.calendarList().list().execute()
        calendars = calendars_result.get('items', [])
        
        if not calendars:
            return "No calendars found"
        
        result = f"📅 **Available Calendars ({len(calendars)} found)**\n\n"
        
        for calendar in calendars:
            cal_id = calendar['id']
            summary = calendar.get('summary', 'No name')
            access_role = calendar.get('accessRole', 'unknown')
            primary = " (Primary)" if calendar.get('primary') else ""
            color_id = calendar.get('colorId', 'default')
            background_color = calendar.get('backgroundColor', '#FFFFFF')
            
            result += f"• **{summary}**{primary}\n"
            result += f"  - ID: `{cal_id}`\n"
            result += f"  - Access: {access_role}\n"
            result += f"  - Color ID: {color_id} ({background_color})\n\n"
        
        return result
    
    def _handle_create_calendar(self, arguments: Dict[str, Any]) -> str:
        """Create a new calendar"""
        summary = arguments["summary"]
        description = arguments.get("description", "")
        timezone = arguments.get("timezone", "UTC")
        
        # Build calendar object
        calendar = {
            'summary': summary,
            'description': description,
            'timeZone': timezone
        }
        
        # Create the calendar
        created_calendar = self.service.calendars().insert(body=calendar).execute()
        
        return f"✅ **Calendar Created Successfully**\n\n" \
               f"• **Name:** {summary}\n" \
               f"• **Calendar ID:** `{created_calendar['id']}`\n" \
               f"• **Timezone:** {timezone}\n" \
               f"• **Description:** {description if description else 'None'}"
    
    def _handle_update_calendar_color(self, arguments: Dict[str, Any]) -> str:
        """Update calendar color"""
        calendar_id = arguments["calendar_id"]
        # Resolve calendar name to ID
        calendar_id = self._resolve_calendar_name_or_id(calendar_id)
        color_id = arguments["color_id"]
        
        # First, get available colors
        colors = self.service.colors().get().execute()
        calendar_colors = colors.get('calendar', {})
        
        if color_id not in calendar_colors:
            available_colors = ", ".join(calendar_colors.keys())
            raise ValueError(f"Invalid Color ID '{color_id}'. Available colors: {available_colors}")
        
        # Update the calendar color
        calendar_list_entry = self.service.calendarList().get(calendarId=calendar_id).execute()
        calendar_list_entry['colorId'] = color_id
        
        updated_calendar = self.service.calendarList().update(
            calendarId=calendar_id, 
            body=calendar_list_entry
        ).execute()
        
        new_color = calendar_colors[color_id]['background']
        
        return f"✅ **Calendar Color Updated**\n\n" \
               f"• **Calendar:** {updated_calendar.get('summary', 'Unknown')}\n" \
               f"• **New Color ID:** {color_id}\n" \
               f"• **Color:** {new_color}"
    
    def _handle_find_time(self, arguments: Dict[str, Any]) -> str:
        """Find free time slots"""
        calendar_id = arguments.get("calendar_id", "primary")
        # Resolve calendar name to ID
        calendar_id = self._resolve_calendar_name_or_id(calendar_id)
        duration_minutes = arguments.get("duration_minutes", 60)
        work_hours_only = arguments.get("work_hours_only", True)
        
        # Handle date range
        start_date = arguments.get("start_date")
        if not start_date:
            start_date = datetime.now().date().isoformat()
        
        end_date = arguments.get("end_date")
        if not end_date:
            start_dt = datetime.fromisoformat(start_date)
            end_dt = start_dt + timedelta(days=7)
            end_date = end_dt.date().isoformat()
        
        # Get existing events
        time_min = f"{start_date}T00:00:00Z"
        time_max = f"{end_date}T23:59:59Z"
        
        events_result = self.service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        # Simple free time finding algorithm
        free_slots = []
        current_date = datetime.fromisoformat(start_date).date()
        end_date_dt = datetime.fromisoformat(end_date).date()
        
        while current_date <= end_date_dt:
            # Work hours: 9 AM to 5 PM
            start_hour = 9 if work_hours_only else 0
            end_hour = 17 if work_hours_only else 24
            
            day_start = datetime.combine(current_date, datetime.min.time().replace(hour=start_hour))
            day_end = datetime.combine(current_date, datetime.min.time().replace(hour=end_hour))
            
            # Find events for this day
            day_events = []
            for event in events:
                event_start = event['start'].get('dateTime', event['start'].get('date'))
                if 'T' in event_start:
                    event_start_dt = datetime.fromisoformat(event_start.replace('Z', '+00:00')).replace(tzinfo=None)
                    event_end = event['end'].get('dateTime', event['end'].get('date'))
                    event_end_dt = datetime.fromisoformat(event_end.replace('Z', '+00:00')).replace(tzinfo=None)
                    
                    if event_start_dt.date() == current_date:
                        day_events.append((event_start_dt, event_end_dt))
            
            # Sort events by start time
            day_events.sort()
            
            # Find gaps
            current_time = day_start
            for event_start, event_end in day_events:
                if current_time + timedelta(minutes=duration_minutes) <= event_start:
                    free_slots.append((current_time, event_start))
                current_time = max(current_time, event_end)
            
            # Check end of day
            if current_time + timedelta(minutes=duration_minutes) <= day_end:
                free_slots.append((current_time, day_end))
            
            current_date += timedelta(days=1)
        
        if not free_slots:
            return f"No free slots of {duration_minutes} minutes found from {start_date} to {end_date}"
        
        result = f"🕐 **Free Time Slots ({len(free_slots)} found)**\n"
        result += f"Duration needed: {duration_minutes} minutes\n\n"
        
        for slot_start, slot_end in free_slots[:10]:  # Limit to first 10 slots
            duration = int((slot_end - slot_start).total_seconds() / 60)
            result += f"• **{slot_start.strftime('%Y-%m-%d %H:%M')} - {slot_end.strftime('%H:%M')}**\n"
            result += f"  Available: {duration} minutes\n\n"
        
        return result
    
    # Calendar CRUD Operations
    def _handle_get_calendar(self, arguments: Dict[str, Any]) -> str:
        """Get calendar details"""
        calendar_id = arguments["calendar_id"]
        calendar_id = self._resolve_calendar_name_or_id(calendar_id)
        
        try:
            calendar = self.service.calendars().get(calendarId=calendar_id).execute()
            calendar_list_entry = self.service.calendarList().get(calendarId=calendar_id).execute()
            
            result = f"📅 **Calendar Details**\n\n"
            result += f"• **Name:** {calendar.get('summary', 'No name')}\n"
            result += f"• **Description:** {calendar.get('description', 'No description')}\n"
            result += f"• **ID:** `{calendar_id}`\n"
            result += f"• **Timezone:** {calendar.get('timeZone', 'Unknown')}\n"
            result += f"• **Access Role:** {calendar_list_entry.get('accessRole', 'Unknown')}\n"
            result += f"• **Color ID:** {calendar_list_entry.get('colorId', 'default')}\n"
            result += f"• **Background Color:** {calendar_list_entry.get('backgroundColor', '#FFFFFF')}\n"
            
            if calendar_list_entry.get('primary'):
                result += f"• **Primary Calendar:** Yes\n"
            
            return result
            
        except Exception as e:
            raise RuntimeError(f"Failed to get calendar: {e}")
    
    def _handle_delete_calendar(self, arguments: Dict[str, Any]) -> str:
        """Delete a calendar"""
        calendar_id = arguments["calendar_id"]
        original_id = calendar_id
        calendar_id = self._resolve_calendar_name_or_id(calendar_id)
        
        try:
            # Get calendar name before deletion
            calendar = self.service.calendars().get(calendarId=calendar_id).execute()
            calendar_name = calendar.get('summary', 'Unknown Calendar')
            
            # Cannot delete primary calendar
            if calendar_id == "primary":
                raise ValueError("The primary calendar cannot be deleted.")
            
            # Delete the calendar
            self.service.calendars().delete(calendarId=calendar_id).execute()
            
            return f"✅ **Calendar Deleted Successfully**\n\n" \
                   f"• **Deleted:** {calendar_name}\n" \
                   f"• **Calendar ID:** `{calendar_id}`\n" \
                   f"⚠️ **Warning:** All events in this calendar have been permanently deleted."
            
        except Exception as e:
            raise RuntimeError(f"Failed to delete calendar: {e}")
    
    def _handle_patch_calendar(self, arguments: Dict[str, Any]) -> str:
        """Partially update calendar properties"""
        calendar_id = arguments["calendar_id"]
        calendar_id = self._resolve_calendar_name_or_id(calendar_id)
        
        try:
            # Build patch data
            patch_data = {}
            if "summary" in arguments:
                patch_data["summary"] = arguments["summary"]
            if "description" in arguments:
                patch_data["description"] = arguments["description"]
            if "timezone" in arguments:
                patch_data["timeZone"] = arguments["timezone"]
            
            if not patch_data:
                raise ValueError("No fields to update were provided.")
            
            # Update the calendar
            updated_calendar = self.service.calendars().patch(
                calendarId=calendar_id,
                body=patch_data
            ).execute()
            
            return f"✅ **Calendar Updated Successfully**\n\n" \
                   f"• **Calendar:** {updated_calendar.get('summary', 'Unknown')}\n" \
                   f"• **Updated Fields:** {list(patch_data.keys())}\n" \
                   f"• **Calendar ID:** `{calendar_id}`"
            
        except Exception as e:
            raise RuntimeError(f"Failed to update calendar: {e}")
    
    # Attendee Management Implementation
    def _handle_add_attendees(self, arguments: Dict[str, Any]) -> str:
        """Add attendees to an event"""
        calendar_id = arguments.get("calendar_id", "primary")
        calendar_id = self._resolve_calendar_name_or_id(calendar_id)
        event_id = arguments["event_id"]
        new_attendees = arguments["attendees"]
        send_notifications = arguments.get("send_notifications", True)
        
        try:
            # Get current event
            event = self.service.events().get(calendarId=calendar_id, eventId=event_id).execute()
            
            # Get current attendees or create empty list
            current_attendees = event.get('attendees', [])
            current_emails = {attendee.get('email', '').lower() for attendee in current_attendees}
            
            # Add new attendees (avoid duplicates)
            added_attendees = []
            for email in new_attendees:
                if email.lower() not in current_emails:
                    current_attendees.append({'email': email})
                    added_attendees.append(email)
            
            if not added_attendees:
                return f"ℹ️ **No New Attendees Added**\n\nAll specified attendees are already invited to this event."
            
            # Update event with new attendees
            event['attendees'] = current_attendees
            
            updated_event = self.service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=event,
                sendUpdates='all' if send_notifications else 'none'
            ).execute()
            
            event_title = updated_event.get('summary', 'Untitled Event')
            
            return f"✅ **Attendees Added Successfully**\n\n" \
                   f"• **Event:** {event_title}\n" \
                   f"• **Added:** {', '.join(added_attendees)}\n" \
                   f"• **Total Attendees:** {len(current_attendees)}\n" \
                   f"• **Notifications Sent:** {'Yes' if send_notifications else 'No'}"
            
        except Exception as e:
            raise RuntimeError(f"Failed to add attendees: {e}")
    
    def _handle_manage_attendee_responses(self, arguments: Dict[str, Any]) -> str:
        """Manage attendee responses"""
        calendar_id = arguments.get("calendar_id", "primary")
        calendar_id = self._resolve_calendar_name_or_id(calendar_id)
        event_id = arguments["event_id"]
        attendee_email = arguments.get("attendee_email")
        response_status = arguments.get("response_status")
        
        try:
            # Get current event
            event = self.service.events().get(calendarId=calendar_id, eventId=event_id).execute()
            event_title = event.get('summary', 'Untitled Event')
            attendees = event.get('attendees', [])
            
            # If no attendees, return info
            if not attendees:
                return f"ℹ️ **No Attendees**\n\nEvent '{event_title}' has no attendees."
            
            # If just viewing attendees (no specific email or status)
            if not attendee_email and not response_status:
                result = f"👥 **Event Attendees ({len(attendees)} total)**\n\n"
                result += f"**Event:** {event_title}\n\n"
                
                for attendee in attendees:
                    email = attendee.get('email', 'Unknown')
                    status = attendee.get('responseStatus', 'needsAction')
                    display_name = attendee.get('displayName', email)
                    organizer = " (Organizer)" if attendee.get('organizer') else ""
                    
                    status_emoji = {
                        'accepted': '✅',
                        'declined': '❌', 
                        'tentative': '❓',
                        'needsAction': '⏳'
                    }.get(status, '❔')
                    
                    result += f"• {status_emoji} **{display_name}**{organizer}\n"
                    result += f"  - Email: {email}\n"
                    result += f"  - Status: {status}\n\n"
                
                return result
            
            # Update specific attendee status
            if attendee_email and response_status:
                updated = False
                for attendee in attendees:
                    if attendee.get('email', '').lower() == attendee_email.lower():
                        attendee['responseStatus'] = response_status
                        updated = True
                        break
                
                if not updated:
                    raise ValueError(f"Attendee '{attendee_email}' is not invited to this event.")
                
                # Update the event
                event['attendees'] = attendees
                self.service.events().update(
                    calendarId=calendar_id,
                    eventId=event_id,
                    body=event
                ).execute()
                
                return f"✅ **Attendee Response Updated**\n\n" \
                       f"• **Event:** {event_title}\n" \
                       f"• **Attendee:** {attendee_email}\n" \
                       f"• **New Status:** {response_status}"
            
            raise ValueError("To update a response, specify both 'attendee_email' and 'response_status'.")
            
        except Exception as e:
            raise RuntimeError(f"Failed to manage attendee responses: {e}")
    
    def _handle_send_invitations(self, arguments: Dict[str, Any]) -> str:
        """Send invitations to attendees"""
        calendar_id = arguments.get("calendar_id", "primary")
        calendar_id = self._resolve_calendar_name_or_id(calendar_id)
        event_id = arguments["event_id"]
        attendee_emails = arguments.get("attendee_emails", [])
        
        try:
            # Get current event
            event = self.service.events().get(calendarId=calendar_id, eventId=event_id).execute()
            event_title = event.get('summary', 'Untitled Event')
            attendees = event.get('attendees', [])
            
            if not attendees:
                return f"ℹ️ **No Attendees**\n\nEvent '{event_title}' has no attendees to send invitations to."
            
            # If specific emails provided, validate they are attendees
            if attendee_emails:
                event_attendee_emails = {a.get('email', '').lower() for a in attendees}
                invalid_emails = [email for email in attendee_emails if email.lower() not in event_attendee_emails]
                
                if invalid_emails:
                    raise ValueError(f"These emails are not attendees of the event: {', '.join(invalid_emails)}")
            
            # Update event to trigger notifications (using patch to minimize changes)
            self.service.events().patch(
                calendarId=calendar_id,
                eventId=event_id,
                body={},  # Empty body to trigger minimal change
                sendUpdates='all'
            ).execute()
            
            recipients = attendee_emails if attendee_emails else [a.get('email') for a in attendees if a.get('email')]
            
            return f"✅ **Invitations Sent Successfully**\n\n" \
                   f"• **Event:** {event_title}\n" \
                   f"• **Recipients:** {', '.join(recipients)}\n" \
                   f"• **Total Sent:** {len(recipients)}"
            
        except Exception as e:
            raise RuntimeError(f"Failed to send invitations: {e}")
    
    # ACL Management Implementation
    def _handle_list_acl_rules(self, arguments: Dict[str, Any]) -> str:
        """List ACL rules for a calendar"""
        calendar_id = arguments["calendar_id"]
        calendar_id = self._resolve_calendar_name_or_id(calendar_id)
        
        try:
            acl_rules = self.service.acl().list(calendarId=calendar_id).execute()
            rules = acl_rules.get('items', [])
            
            if not rules:
                return f"📋 **No Sharing Rules**\n\nCalendar has no access control rules."
            
            # Get calendar name for display
            calendar = self.service.calendars().get(calendarId=calendar_id).execute()
            calendar_name = calendar.get('summary', 'Unknown Calendar')
            
            result = f"🔐 **Calendar Sharing Rules ({len(rules)} rules)**\n\n"
            result += f"**Calendar:** {calendar_name}\n\n"
            
            for rule in rules:
                rule_id = rule['id']
                role = rule['role']
                scope = rule['scope']
                scope_type = scope['type']
                scope_value = scope.get('value', 'N/A')
                
                role_emoji = {
                    'owner': '👑',
                    'writer': '✏️',
                    'reader': '👁️',
                    'freeBusyReader': '📅'
                }.get(role, '❔')
                
                scope_display = {
                    'user': f"User: {scope_value}",
                    'group': f"Group: {scope_value}",
                    'domain': f"Domain: {scope_value}",
                    'default': "Public access"
                }.get(scope_type, f"{scope_type}: {scope_value}")
                
                result += f"• {role_emoji} **{role.title()}** - {scope_display}\n"
                result += f"  - Rule ID: `{rule_id}`\n\n"
            
            return result
            
        except Exception as e:
            raise RuntimeError(f"Failed to list ACL rules: {e}")
    
    def _handle_insert_acl_rule(self, arguments: Dict[str, Any]) -> str:
        """Insert new ACL rule"""
        calendar_id = arguments["calendar_id"]
        calendar_id = self._resolve_calendar_name_or_id(calendar_id)
        role = arguments["role"]
        scope_type = arguments["scope_type"]
        scope_value = arguments.get("scope_value")
        send_notifications = arguments.get("send_notifications", True)
        
        try:
            # Build ACL rule
            acl_rule = {
                'role': role,
                'scope': {
                    'type': scope_type
                }
            }
            
            # Add scope value if provided and required
            if scope_type in ['user', 'group', 'domain'] and scope_value:
                acl_rule['scope']['value'] = scope_value
            elif scope_type in ['user', 'group', 'domain'] and not scope_value:
                raise ValueError(f"Scope type '{scope_type}' requires a 'scope_value' (e.g., email or domain).")
            
            # Insert the ACL rule
            inserted_rule = self.service.acl().insert(
                calendarId=calendar_id,
                body=acl_rule,
                sendNotifications=send_notifications
            ).execute()
            
            # Get calendar name for display
            calendar = self.service.calendars().get(calendarId=calendar_id).execute()
            calendar_name = calendar.get('summary', 'Unknown Calendar')
            
            scope_display = {
                'user': f"User: {scope_value}",
                'group': f"Group: {scope_value}",
                'domain': f"Domain: {scope_value}",
                'default': "Public access"
            }.get(scope_type, f"{scope_type}: {scope_value}")
            
            return f"✅ **Calendar Shared Successfully**\n\n" \
                   f"• **Calendar:** {calendar_name}\n" \
                   f"• **Access Level:** {role}\n" \
                   f"• **Shared With:** {scope_display}\n" \
                   f"• **Rule ID:** `{inserted_rule['id']}`\n" \
                   f"• **Notification Sent:** {'Yes' if send_notifications else 'No'}"
            
        except Exception as e:
            raise RuntimeError(f"Failed to share calendar: {e}")
    
    def _handle_update_acl_rule(self, arguments: Dict[str, Any]) -> str:
        """Update existing ACL rule"""
        calendar_id = arguments["calendar_id"]
        calendar_id = self._resolve_calendar_name_or_id(calendar_id)
        rule_id = arguments["rule_id"]
        role = arguments["role"]
        
        try:
            # Get existing rule
            existing_rule = self.service.acl().get(calendarId=calendar_id, ruleId=rule_id).execute()
            
            # Update only the role
            existing_rule['role'] = role
            
            # Update the rule
            updated_rule = self.service.acl().update(
                calendarId=calendar_id,
                ruleId=rule_id,
                body=existing_rule
            ).execute()
            
            # Get calendar name and scope info for display
            calendar = self.service.calendars().get(calendarId=calendar_id).execute()
            calendar_name = calendar.get('summary', 'Unknown Calendar')
            
            scope = updated_rule['scope']
            scope_type = scope['type']
            scope_value = scope.get('value', 'N/A')
            
            scope_display = {
                'user': f"User: {scope_value}",
                'group': f"Group: {scope_value}",
                'domain': f"Domain: {scope_value}",
                'default': "Public access"
            }.get(scope_type, f"{scope_type}: {scope_value}")
            
            return f"✅ **Sharing Permissions Updated**\n\n" \
                   f"• **Calendar:** {calendar_name}\n" \
                   f"• **Target:** {scope_display}\n" \
                   f"• **New Access Level:** {role}\n" \
                   f"• **Rule ID:** `{rule_id}`"
            
        except Exception as e:
            raise RuntimeError(f"Failed to update ACL rule: {e}")
    
    def _handle_delete_acl_rule(self, arguments: Dict[str, Any]) -> str:
        """Delete ACL rule"""
        calendar_id = arguments["calendar_id"]
        calendar_id = self._resolve_calendar_name_or_id(calendar_id)
        rule_id = arguments["rule_id"]
        
        try:
            # Get rule info before deletion
            rule = self.service.acl().get(calendarId=calendar_id, ruleId=rule_id).execute()
            scope = rule['scope']
            scope_type = scope['type']
            scope_value = scope.get('value', 'N/A')
            role = rule['role']
            
            scope_display = {
                'user': f"User: {scope_value}",
                'group': f"Group: {scope_value}",
                'domain': f"Domain: {scope_value}",
                'default': "Public access"
            }.get(scope_type, f"{scope_type}: {scope_value}")
            
            # Delete the rule
            self.service.acl().delete(calendarId=calendar_id, ruleId=rule_id).execute()
            
            # Get calendar name for display
            calendar = self.service.calendars().get(calendarId=calendar_id).execute()
            calendar_name = calendar.get('summary', 'Unknown Calendar')
            
            return f"✅ **Calendar Access Revoked**\n\n" \
                   f"• **Calendar:** {calendar_name}\n" \
                   f"• **Revoked From:** {scope_display}\n" \
                   f"• **Previous Access:** {role}\n" \
                   f"• **Rule ID:** `{rule_id}`"
            
        except Exception as e:
            raise RuntimeError(f"Failed to revoke access: {e}")
    
    # Reminders and Conference Implementation
    def _handle_add_reminders(self, arguments: Dict[str, Any]) -> str:
        """Add reminders to an event"""
        calendar_id = arguments.get("calendar_id", "primary")
        calendar_id = self._resolve_calendar_name_or_id(calendar_id)
        event_id = arguments["event_id"]
        reminders = arguments["reminders"]
        
        try:
            # Get current event
            event = self.service.events().get(calendarId=calendar_id, eventId=event_id).execute()
            event_title = event.get('summary', 'Untitled Event')
            
            # Build reminders structure
            reminder_overrides = []
            for reminder in reminders:
                reminder_overrides.append({
                    'method': reminder['method'],
                    'minutes': int(reminder['minutes'])
                })
            
            # Update event with reminders
            event['reminders'] = {
                'useDefault': False,
                'overrides': reminder_overrides
            }
            
            updated_event = self.service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=event
            ).execute()
            
            result = f"⏰ **Reminders Added Successfully**\n\n"
            result += f"• **Event:** {event_title}\n"
            result += f"• **Reminders Added:**\n"
            
            for reminder in reminders:
                method = reminder['method']
                minutes = reminder['minutes']
                method_emoji = '📧' if method == 'email' else '🔔'
                
                if minutes < 60:
                    time_str = f"{minutes} minutes"
                elif minutes < 1440:
                    hours = minutes // 60
                    remaining_mins = minutes % 60
                    time_str = f"{hours}h {remaining_mins}m" if remaining_mins else f"{hours} hours"
                else:
                    days = minutes // 1440
                    remaining_hours = (minutes % 1440) // 60
                    time_str = f"{days}d {remaining_hours}h" if remaining_hours else f"{days} days"
                
                result += f"  - {method_emoji} {method.title()}: {time_str} before\n"
            
            return result
            
        except Exception as e:
            raise RuntimeError(f"Failed to add reminders: {e}")
    
    def _handle_add_conference_data(self, arguments: Dict[str, Any]) -> str:
        """Add conference data to an event"""
        calendar_id = arguments.get("calendar_id", "primary")
        calendar_id = self._resolve_calendar_name_or_id(calendar_id)
        event_id = arguments["event_id"]
        solution_type = arguments.get("conference_solution_type", "hangoutsMeet")
        create_request = arguments.get("create_request", True)
        conference_id = arguments.get("conference_id")
        
        try:
            # Get current event
            event = self.service.events().get(calendarId=calendar_id, eventId=event_id).execute()
            event_title = event.get('summary', 'Untitled Event')
            
            if create_request:
                # Create new conference request
                import uuid
                request_id = str(uuid.uuid4())
                
                event['conferenceData'] = {
                    'createRequest': {
                        'requestId': request_id,
                        'conferenceSolutionKey': {
                            'type': solution_type
                        }
                    }
                }
            else:
                if not conference_id:
                    raise ValueError("When 'create_request' is false, a 'conference_id' must be provided.")
                
                # Use existing conference
                event['conferenceData'] = {
                    'conferenceId': conference_id,
                    'conferenceSolution': {
                        'key': {
                            'type': solution_type
                        }
                    }
                }
            
            # Update the event
            updated_event = self.service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=event,
                conferenceDataVersion=1
            ).execute()
            
            # Get conference data from response
            conference_data = updated_event.get('conferenceData', {})
            
            result = f"🎥 **Conference Data Added Successfully**\n\n"
            result += f"• **Event:** {event_title}\n"
            result += f"• **Conference Type:** {solution_type}\n"
            
            if create_request:
                result += f"• **Conference Creation:** Requested\n"
                
                # Check if conference was created
                entry_points = conference_data.get('entryPoints', [])
                if entry_points:
                    for entry_point in entry_points:
                        if entry_point.get('entryPointType') == 'video':
                            result += f"• **Meet Link:** {entry_point.get('uri', 'Pending...')}\n"
                        elif entry_point.get('entryPointType') == 'phone':
                            result += f"• **Phone:** {entry_point.get('uri', 'N/A')}\n"
                else:
                    result += f"• **Meet Link:** Generating...\n"
            else:
                result += f"• **Conference ID:** {conference_id}\n"
            
            return result
            
        except Exception as e:
            raise RuntimeError(f"Failed to add conference data: {e}")

def main():
    """Main entry point"""
    server = GoogleCalendarServer()
    server.run()

if __name__ == "__main__":
    main()

```

`mcp_handley_lab/jq/README.md`:

```md
# JQ MCP Server

A Model Context Protocol (MCP) server that provides JSON querying, editing, and manipulation capabilities using the powerful [jq](https://stedolan.github.io/jq/) command-line tool.

## Features

- **Query JSON**: Extract data using jq filter expressions
- **Edit JSON Files**: Modify JSON files in-place with transformations
- **Read JSON**: Pretty-print and display JSON files
- **Validate JSON**: Check JSON syntax and structure
- **Format JSON**: Pretty-print or compact JSON data

## Prerequisites

The `jq` command-line tool must be installed on your system:

- **Ubuntu/Debian**: `sudo apt-get install jq`
- **macOS**: `brew install jq`
- **Arch Linux**: `sudo pacman -S jq`
- **Windows**: Download from [jq website](https://stedolan.github.io/jq/download/)

## Tools

### query
Query JSON data using jq filter expressions.

**Parameters:**
- `data` (required): JSON data as string or file path
- `filter`: jq filter expression (default: ".")
- `raw_output`: Output raw strings instead of JSON (default: false)
- `compact`: Compact output instead of pretty-printed (default: false)

**Examples:**
- Extract name: `filter: ".name"`
- Get array items: `filter: ".items[]"`
- Map transformation: `filter: ".users | map(.email)"`

### edit
Edit JSON files using jq transformations.

**Parameters:**
- `file_path` (required): Path to JSON file to edit
- `filter` (required): jq transformation expression
- `backup`: Create backup before editing (default: true)

**Examples:**
- Update field: `filter: ".name = \"new_name\""`
- Delete field: `filter: "del(.unwanted_field)"`
- Add field: `filter: ".new_field = \"value\""`

### read
Read and display JSON files with optional filtering.

**Parameters:**
- `file_path` (required): Path to JSON file
- `filter`: Optional jq filter to apply (default: ".")

### validate
Validate JSON syntax and structure.

**Parameters:**
- `data` (required): JSON data as string or file path

### format
Format and pretty-print JSON data.

**Parameters:**
- `data` (required): JSON data as string or file path
- `compact`: Output compact JSON (default: false)
- `sort_keys`: Sort object keys alphabetically (default: false)

### server_info
Get server status and jq version information.

## Usage Examples

### Query JSON Data
```json
{
  "name": "query",
  "arguments": {
    "data": "{\"users\": [{\"name\": \"Alice\", \"age\": 30}, {\"name\": \"Bob\", \"age\": 25}]}",
    "filter": ".users | map(.name)"
  }
}
```

### Edit JSON File
```json
{
  "name": "edit",
  "arguments": {
    "file_path": "/path/to/config.json",
    "filter": ".debug = true | .port = 8080"
  }
}
```

### Validate JSON
```json
{
  "name": "validate",
  "arguments": {
    "data": "{\"valid\": \"json\"}"
  }
}
```

## Installation

1. Ensure `jq` is installed on your system
2. Add the server to your MCP configuration
3. Start using JSON manipulation tools in Claude Code

## Testing

Run the test suite:
```bash
python test_jq.py
```

## jq Filter Reference

Common jq patterns:
- `.` - Identity (returns input unchanged)
- `.field` - Extract field value
- `.[]` - Array/object value iterator
- `.[0]` - First array element
- `.field1.field2` - Nested field access
- `map(.field)` - Transform array elements
- `select(.field == "value")` - Filter elements
- `length` - Get array/object length
- `keys` - Get object keys
- `del(.field)` - Delete field
- `sort_by(.field)` - Sort array by field

For comprehensive documentation, see the [jq manual](https://stedolan.github.io/jq/manual/).
```

`mcp_handley_lab/jq/requirements.txt`:

```txt
# No Python dependencies - relies on system jq installation
# Install jq using:
# - Ubuntu/Debian: sudo apt-get install jq
# - macOS: brew install jq
# - Arch Linux: sudo pacman -S jq
# - Windows: Download from https://stedolan.github.io/jq/download/
```

`mcp_handley_lab/jq/schemas.yml`:

```yml
tools:
  server_info:
    name: server_info
    description: Get JQ server status and error information
    inputSchema:
      type: object
      properties: {}
      required: []
    annotations:
      title: JQ Server Info
      readOnlyHint: true
      destructiveHint: false
      idempotentHint: true
      openWorldHint: false

  query:
    name: query
    description: Queries JSON data from a string or file using a jq filter expression and returns the result.
    inputSchema:
      type: object
      properties:
        data:
          type: string
          description: JSON data as a string or a file path. File paths are auto-detected.
        filter:
          type: string
          description: "Optional. The jq filter expression to apply (e.g., '.name', '.items[]', '.users | map(.email)'). Defaults to '.' (identity, returning the entire input)."
          default: "."
        raw_output:
          type: boolean
          description: "Optional. If true, outputs raw strings (e.g., a simple value like 'hello') instead of JSON-quoted text. Defaults to false (output is JSON-formatted)."
          default: false
        compact:
          type: boolean
          description: "Optional. If true, outputs compact JSON on a single line. If false (default), outputs pretty-printed JSON with indentation. Defaults to false."
          default: false
      required: [data]
    annotations:
      title: Query JSON with JQ
      readOnlyHint: true
      destructiveHint: false
      idempotentHint: true
      openWorldHint: false

  edit:
    name: edit
    description: Edit JSON files using jq filter expressions
    inputSchema:
      type: object
      properties:
        file_path:
          type: string
          description: Path to JSON file to edit
        filter:
          type: string
          description: "jq filter expression to transform the data (e.g., '.name = \"new_name\"', 'del(.unwanted_field)')"
        backup:
          type: boolean
          description: Create backup file before editing
          default: true
      required: [file_path, filter]
    annotations:
      title: Edit JSON with JQ
      readOnlyHint: false
      destructiveHint: true
      idempotentHint: false
      openWorldHint: false

  read:
    name: read
    description: Read and pretty-print JSON files
    inputSchema:
      type: object
      properties:
        file_path:
          type: string
          description: Path to JSON file to read
        filter:
          type: string
          description: Optional jq filter to apply while reading
          default: "."
      required: [file_path]
    annotations:
      title: Read JSON File
      readOnlyHint: true
      destructiveHint: false
      idempotentHint: true
      openWorldHint: false

  validate:
    name: validate
    description: Validate JSON syntax and structure
    inputSchema:
      type: object
      properties:
        data:
          type: string
          description: JSON data to validate (as string) or file path to JSON file
      required: [data]
    annotations:
      title: Validate JSON
      readOnlyHint: true
      destructiveHint: false
      idempotentHint: true
      openWorldHint: false

  format:
    name: format
    description: Format and pretty-print JSON data
    inputSchema:
      type: object
      properties:
        data:
          type: string
          description: JSON data to format (as string) or file path to JSON file
        compact:
          type: boolean
          description: Output compact JSON instead of pretty-printed
          default: false
        sort_keys:
          type: boolean
          description: Sort object keys alphabetically
          default: false
      required: [data]
    annotations:
      title: Format JSON
      readOnlyHint: true
      destructiveHint: false
      idempotentHint: true
      openWorldHint: false
```

`mcp_handley_lab/jq/server.py`:

```py
#!/usr/bin/env python3
"""
FastMCP-based JQ Server
Modern implementation using the official python-sdk
"""

import os
import json
import subprocess
import shutil
import tempfile
import uuid
from typing import Dict, Any, List, Optional, Union

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations, ErrorData, INTERNAL_ERROR, INVALID_PARAMS
from mcp.shared.exceptions import McpError
from pydantic_settings import BaseSettings


class JQSettings(BaseSettings):
    """Settings for JQ server"""
    cli_command: str = "jq"
    
    class Config:
        env_prefix = "JQ_"


# Initialize settings and jq availability at module level
settings = JQSettings()

# Check if jq CLI is available
jq_available = False
error_message = ""
cli_command = settings.cli_command

if shutil.which(settings.cli_command):
    jq_available = True
    cli_command = settings.cli_command
    error_message = ""
else:
    jq_available = False
    error_message = f"jq CLI not found. Please install it first: apt-get install jq (Ubuntu/Debian) or brew install jq (macOS)"


# Create FastMCP app
mcp = FastMCP(
    "JQ MCP Server",
    instructions="Provides JSON querying, editing, and manipulation using the jq command-line processor."
)


def run_jq_command(args: List[str], input_data: str = "") -> Dict[str, Any]:
    """Run jq command and return result"""
    if not jq_available:
        return {
            "success": False,
            "error": error_message,
            "output": "",
            "stderr": ""
        }
    
    try:
        cmd = [cli_command] + args
        result = subprocess.run(
            cmd,
            input=input_data,
            capture_output=True,
            text=True
        )
        
        return {
            "success": result.returncode == 0,
            "output": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "command": " ".join(cmd)
        }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Command timed out after 30 seconds",
            "output": "",
            "stderr": ""
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "output": "",
            "stderr": ""
        }


def detect_json_source(data: str) -> tuple[str, bool]:
    """Detect if data is a file path or JSON string"""
    # Check if it looks like a file path and the file exists
    if (not data.strip().startswith('{') and 
        not data.strip().startswith('[') and 
        os.path.exists(data.strip())):
        return data.strip(), True
    else:
        return data, False


@mcp.tool(
    name="query",
    description="Queries JSON data using a jq filter. The data parameter can be a JSON string or a path to a JSON file.",
    annotations=ToolAnnotations(
        title="Query JSON with JQ",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False
    )
)
def query(
    data: Union[str, dict, list],
    filter: str = ".",
    compact: bool = False,
    raw_output: bool = False
) -> str:
    """Query JSON data using jq filter"""
    
    if not jq_available:
        raise RuntimeError(f"jq CLI not available: {error_message}")
    
    try:
        # Convert data to JSON string if it's a dict or list
        if isinstance(data, (dict, list)):
            data_json_string = json.dumps(data)
        elif isinstance(data, str):
            data_json_string = data
        else:
            raise ValueError(f"Unsupported data type for jq: {type(data)}")
        
        # Detect if data is file path or JSON string
        data_source, is_file = detect_json_source(data_json_string)
        
        # Build jq command args
        args = []
        
        if compact:
            args.append("-c")
        
        if raw_output:
            args.append("-r")
        
        args.append(filter)
        
        if is_file:
            args.append(data_source)
            input_data = ""
        else:
            input_data = data_source
        
        # Run jq command
        result = run_jq_command(args, input_data)
        
        if not result["success"]:
            error_msg = result.get("error") or result.get("stderr") or "Unknown error"
            raise McpError(error=ErrorData(code=INTERNAL_ERROR, message=f"jq query failed: {error_msg}"))
        
        output = result["output"].rstrip('\n')
        
        if not output:
            return "null"
        
        return output
        
    except McpError:
        # Re-raise McpError as-is
        raise
    except Exception as e:
        raise McpError(error=ErrorData(code=INTERNAL_ERROR, message=f"jq query failed: {e}"))


@mcp.tool(
    name="edit",
    description="Edits a JSON file in-place using a jq transformation filter. Requires a direct file_path.",
    annotations=ToolAnnotations(
        title="Edit JSON File with JQ",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False
    )
)
def edit(
    file_path: str,
    filter: str,
    backup: bool = True
) -> str:
    """Edit JSON file using jq filter"""
    
    if not jq_available:
        raise RuntimeError(f"jq CLI not available: {error_message}")
    
    try:
        # Validate file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File does not exist: {file_path}")
        
        # Create backup if requested
        if backup:
            backup_path = f"{file_path}.backup"
            shutil.copy2(file_path, backup_path)
        
        # Read original file
        with open(file_path, 'r') as f:
            original_content = f.read()
        
        # Run jq to transform the data
        args = [filter, file_path]
        result = run_jq_command(args)
        
        if not result["success"]:
            error_msg = result.get("error") or result.get("stderr") or "Unknown error"
            raise RuntimeError(f"jq edit failed: {error_msg}")
        
        # Write the result back to the file
        with open(file_path, 'w') as f:
            f.write(result["output"])
        
        success_msg = f"""✅ **JSON File Edited Successfully**

📁 **File:** `{file_path}`
🔧 **Filter:** `{filter}`
{f'💾 **Backup:** `{backup_path}`' if backup else '⚠️ **No Backup Created**'}

💡 **Result:** File has been updated with the jq transformation."""
        
        return success_msg
        
    except Exception as e:
        raise RuntimeError(f"jq edit failed: {e}")


@mcp.tool(
    name="read",
    description="Reads and pretty-prints a JSON file. Applies an optional jq filter. Requires a direct file_path.",
    annotations=ToolAnnotations(
        title="Read JSON File",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False
    )
)
def read(
    file_path: str,
    filter: str = "."
) -> str:
    """Read and format JSON file"""
    
    if not jq_available:
        raise RuntimeError(f"jq CLI not available: {error_message}")
    
    try:
        # Validate file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File does not exist: {file_path}")
        
        # Run jq to read and format
        args = [filter, file_path]
        result = run_jq_command(args)
        
        if not result["success"]:
            error_msg = result.get("error") or result.get("stderr") or "Unknown error"
            raise RuntimeError(f"jq read failed: {error_msg}")
        
        output = result["output"].rstrip('\n')
        
        if not output:
            return "null"
        
        return output
        
    except Exception as e:
        raise RuntimeError(f"jq read failed: {e}")


@mcp.tool(
    name="validate",
    description="Validates the syntax of JSON data. The data parameter can be a JSON string or a path to a JSON file.",
    annotations=ToolAnnotations(
        title="Validate JSON",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False
    )
)
def validate(data: str) -> str:
    """Validate JSON data"""
    
    if not jq_available:
        raise RuntimeError(f"jq CLI not available: {error_message}")
    
    try:
        # Detect if data is file path or JSON string
        data_source, is_file = detect_json_source(data)
        
        # Build jq command for validation (just parse, don't transform)
        args = ["empty"]
        
        if is_file:
            args.append(data_source)
            input_data = ""
        else:
            input_data = data_source
        
        # Run jq command
        result = run_jq_command(args, input_data)
        
        if result["success"]:
            source_type = "file" if is_file else "string"
            return f"✅ **Valid JSON**\n\n📄 **Source:** {source_type}\n✨ **Status:** JSON syntax is valid"
        else:
            error_msg = result.get("stderr") or result.get("error") or "Unknown validation error"
            raise ValueError(f"Invalid JSON: {error_msg}")
        
    except Exception as e:
        raise RuntimeError(f"jq validation failed: {e}")


@mcp.tool(
    name="format",
    description="Pretty-prints or compacts JSON data. The data parameter can be a JSON string or a path to a JSON file.",
    annotations=ToolAnnotations(
        title="Format JSON",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False
    )
)
def format(
    data: str,
    compact: bool = False,
    sort_keys: bool = False
) -> str:
    """Format JSON data"""
    
    if not jq_available:
        raise RuntimeError(f"jq CLI not available: {error_message}")
    
    try:
        # Detect if data is file path or JSON string
        data_source, is_file = detect_json_source(data)
        
        # Build jq command args
        args = []
        
        if compact:
            args.append("-c")
        
        if sort_keys:
            args.append("-S")
        
        args.append(".")
        
        if is_file:
            args.append(data_source)
            input_data = ""
        else:
            input_data = data_source
        
        # Run jq command
        result = run_jq_command(args, input_data)
        
        if not result["success"]:
            error_msg = result.get("error") or result.get("stderr") or "Unknown error"
            raise RuntimeError(f"jq format failed: {error_msg}")
        
        output = result["output"].rstrip('\n')
        
        if not output:
            return "null"
        
        return output
        
    except Exception as e:
        raise RuntimeError(f"jq format failed: {e}")


@mcp.tool(
    name="server_info",
    description="Checks the status of the jq server and verifies that the jq CLI tool is installed and available.",
    annotations=ToolAnnotations(
        title="JQ Server Status",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False
    )
)
def server_info() -> str:
    """Get server status and configuration info"""
    if jq_available:
        # Get version info
        version_result = run_jq_command(["--version"])
        version_info = version_result.get("output", "Unknown").strip() if version_result["success"] else "Unknown"
        
        return f"""✅ **JQ Server Available**

🔧 **Configuration:**
- CLI Command: {cli_command}
- Version: {version_info}

🛠️ **Available Tools:**
- query: Query JSON data with jq filters
- edit: Edit JSON files using jq transformations
- read: Read and pretty-print JSON files
- validate: Validate JSON syntax and structure
- format: Format and pretty-print JSON data
- server_info: This status information

💡 **Usage Tips:**
- Use '.' for identity filter (no transformation)
- File paths are auto-detected vs JSON strings
- Backup is created by default when editing files
- Use compact=true for single-line output
- Use raw_output=true for unquoted strings

📖 **JQ Manual:** https://stedolan.github.io/jq/manual/"""
    else:
        return f"""❌ **JQ Server Unavailable**

🔴 **Error:** {error_message}

🔧 **Setup Required:**
1. Install jq command-line tool:
   - Ubuntu/Debian: `sudo apt-get install jq`
   - macOS: `brew install jq`
   - Windows: Download from https://stedolan.github.io/jq/download/
2. Restart the server

📚 **More Info:** https://stedolan.github.io/jq/"""


def main():
    """Main entry point"""
    # Run with stdio transport (synchronous)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
```

`mcp_handley_lab/llm/__init__.py`:

```py
"""
LLM MCP server utilities and shared components
"""

from mcp_handley_lab.llm.utils import (
    FileInput,
    normalize_file_inputs,
    aggregate_file_contents,
    format_file_contents_simple,
    format_file_contents_for_llm,
    normalize_image_inputs,
    get_multi_image_analysis_prompt,
    merge_messages_for_prompt,
    merge_system_messages_for_api
)
from mcp_handley_lab.llm.usage_tracker import usage_tracker, estimate_tokens, estimate_openai_tokens
from mcp_handley_lab.llm.config import ModelDefaults, TokenLimits, get_config

__all__ = [
    'FileInput',
    'normalize_file_inputs',
    'aggregate_file_contents',
    'format_file_contents_simple',
    'format_file_contents_for_llm',
    'normalize_image_inputs',
    'get_multi_image_analysis_prompt',
    'merge_messages_for_prompt',
    'merge_system_messages_for_api',
    'usage_tracker',
    'estimate_tokens',
    'estimate_openai_tokens',
    'ModelDefaults',
    'TokenLimits', 
    'get_config'
]
```

`mcp_handley_lab/llm/config.py`:

```py
"""
Configuration management for MCP servers
"""

import os
from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class ServerConfig:
    """Configuration settings for MCP servers"""
    
    # General defaults (truly global)
    default_temperature: float = 0.7
    
    # Request timeouts (None = no timeout)
    api_timeout_seconds: Optional[int] = None
    image_download_timeout: int = 30
    
    # Usage tracking
    usage_log_file: Optional[str] = None  # None = default to ~/.claude_mcp_usage.json
    
    
    @classmethod
    def from_env(cls) -> 'ServerConfig':
        """Load configuration from environment variables"""
        return cls(
            default_temperature=float(os.environ.get('MCP_DEFAULT_TEMPERATURE', '0.7')),
            api_timeout_seconds=int(os.environ.get('MCP_API_TIMEOUT')) if os.environ.get('MCP_API_TIMEOUT') else None,
            image_download_timeout=int(os.environ.get('MCP_IMAGE_TIMEOUT', '30')),
            usage_log_file=os.environ.get('MCP_USAGE_LOG_FILE')
        )

# Model-specific constants
class ModelDefaults:
    """Default model settings for different providers"""
    
    # OpenAI models
    OPENAI_DEFAULT_MODEL = "gpt-4o"
    OPENAI_DEFAULT_IMAGE_MODEL = "dall-e-3"
    OPENAI_MATH_MODEL = "o1-preview"
    
    # Gemini models
    GEMINI_DEFAULT_MODEL = "flash"  # maps to gemini-2.5-flash-preview-05-20
    GEMINI_SMART_MODEL = "pro"      # maps to gemini-2.5-pro-preview-06-05
    GEMINI_DEFAULT_IMAGE_MODEL = "image-flash"
    
    # Temperature settings
    CREATIVE_TEMPERATURE = 0.8      # For brainstorming
    PRECISE_TEMPERATURE = 0.2       # For code review
    MATH_TEMPERATURE = 0.1          # For mathematical reasoning

class TokenLimits:
    """Model-specific token limits (based on documented API limits)"""
    
    # OpenAI models (max_tokens parameter) - well documented
    OPENAI_STANDARD = 4096
    OPENAI_LARGE = 8192
    
    # OpenAI o1 models (max_completion_tokens parameter) - well documented  
    OPENAI_O1_STANDARD = 4096
    OPENAI_O1_LARGE = 8192
    
    # Gemini models - let the API handle limits, don't hard-code
    # Different Gemini models have different context windows and the limits
    # can change. Better to let the API reject with proper error messages.
    
    @staticmethod
    def get_openai_limit(model: str) -> int:
        """Get appropriate token limit for OpenAI model"""
        if model.startswith(("o1-", "o3", "o4")):  # All reasoning models
            return TokenLimits.OPENAI_O1_STANDARD
        elif model in ["gpt-4", "gpt-4-turbo", "gpt-4.1"]:
            return TokenLimits.OPENAI_LARGE
        else:
            return TokenLimits.OPENAI_STANDARD
    
    @staticmethod
    def get_gemini_limit(model_key: str) -> Optional[int]:
        """Get Gemini token limit if known, otherwise None (let API handle it)"""
        # Don't hard-code Gemini limits - they vary by model and can change
        # Let the API return proper error messages if limits are exceeded
        return None


# Global configuration instance
config = ServerConfig.from_env()

def get_config() -> ServerConfig:
    """Get the global configuration instance"""
    return config


```

`mcp_handley_lab/llm/gemini/README.md`:

```md
# Gemini MCP Server

Google Gemini AI integration for Claude Code via Model Context Protocol.

## Quick Setup

1. **Get API Key**: [Google AI Studio](https://aistudio.google.com/app/apikey)
2. **Set Environment Variable**: `export GEMINI_API_KEY="your-key"`
3. **Install Dependencies**: `pip install -r requirements.txt`
4. **Register Server**: `claude config mcp add gemini --scope user --command "python /path/to/gemini/server.py"`

## Gemini-Specific Features

### 🧠 **Intelligent Model Selection**
- **Flash** (default): Fast responses for general queries
- **Pro**: Automatically used for complex tasks (code review, brainstorming)
- **Specialized**: TTS, image generation, video generation

### 🔍 **Google Search Integration**
- Real-time web search grounding
- Automatically enabled for queries that benefit from current information
- Toggle with `grounding` parameter

### 🎨 **Advanced Generation Models**
- **Imagen 3.0**: High-quality image generation
- **Veo 2.0**: Video generation capabilities
- **Text-to-Speech**: Both flash and pro quality levels

### 🧮 **Mathematical Reasoning**
- Step-by-step problem solving
- Show/hide work with `show_work` parameter
- Optimized for mathematical accuracy

## Available Tools

- **`ask_gemini`** - Text generation with optional search grounding
- **`gemini_code_review`** - Code analysis (auto-uses Pro model)
- **`gemini_brainstorm`** - Creative ideation (auto-uses Pro model)
- **`gemini_generate_image`** - Image creation with Imagen models
- **`gemini_math_reasoner`** - Mathematical problem solving

## Usage Examples

```python
# Quick question (uses Flash)
ask_gemini("What is Python?")

# Complex analysis (auto-switches to Pro)
gemini_code_review(code="def divide(a, b): return a / b")

# Search-grounded query
ask_gemini("Latest developments in quantum computing", grounding=True)

# High-quality image
gemini_generate_image("Serene mountain landscape", model="image")

# Math problem solving
gemini_math_reasoner("Solve: x² + 5x - 6 = 0", show_work=True)
```

## Models

### Text Models
- `flash`: `gemini-2.5-flash-preview-05-20` (default)
- `pro`: `gemini-2.5-pro-preview-06-05`
- `tts-flash`: Text-to-speech (fast)
- `tts-pro`: Text-to-speech (high quality)

### Visual Models
- `image`: Imagen 3.0 (high quality)
- `image-flash`: Fast image generation (default)
- `video`: Veo 2.0 video generation

---

📚 **For complete documentation, setup instructions, and troubleshooting**, see the [main README](../README.md).
```

`mcp_handley_lab/llm/gemini/requirements.txt`:

```txt
google-generativeai>=0.8.0
```

`mcp_handley_lab/llm/gemini/server.py`:

```py
#!/usr/bin/env python3
"""
FastMCP-based Gemini Server
Modern implementation using the official python-sdk
"""

import os
import base64
from typing import Dict, Any, List, Optional, Union
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic_settings import BaseSettings

# Import existing utilities we want to keep
from mcp_handley_lab.llm import (
    estimate_tokens, usage_tracker, ModelDefaults
)
from mcp_handley_lab.llm.utils import normalize_file_inputs, format_file_contents_for_llm
from mcp_handley_lab.constants import PLACEHOLDER_API_KEY
from mcp_handley_lab.memory import AgentMemory


class GeminiSettings(BaseSettings):
    """Settings for Gemini server"""
    api_key: str = ""
    default_model: str = "flash"
    default_temperature: float = 0.7
    
    class Config:
        env_prefix = "GEMINI_"


# Available Gemini models
AVAILABLE_MODELS = {
    "flash": "gemini-2.5-flash-preview-05-20",
    "pro": "gemini-2.5-pro-preview-06-05", 
    "tts-flash": "gemini-2.5-flash-preview-tts",
    "tts-pro": "gemini-2.5-pro-preview-tts",
    "image": "imagen-3.0-generate-002",
    "image-flash": "imagen-3.0-generate-002",
    "video": "veo-2.0-generate-001",
}


# Initialize settings and clients at module level
settings = GeminiSettings()

# Initialize memory system
import tempfile
memory_dir = os.environ.get("MCP_MEMORY_DIR", os.path.join(tempfile.gettempdir(), "mcp_agent_memory"))
memory = AgentMemory(memory_dir)

# Initialize Gemini client
gemini_available = False
error_message = ""
genai = None
genai_client = None
model_instances = {}

if not settings.api_key or settings.api_key == PLACEHOLDER_API_KEY:
    gemini_available = False
    error_message = "Please set GEMINI_API_KEY environment variable"
else:
    try:
        import google.generativeai as genai
        from google import genai as genai_client_module
        from google.genai.types import Tool, GenerateContentConfig, GenerateImagesConfig, GoogleSearch
        
        genai.configure(api_key=settings.api_key)
        genai_client = genai_client_module.Client(api_key=settings.api_key)
        gemini_available = True
        
    except Exception as e:
        gemini_available = False
        error_message = str(e)


# Create FastMCP app
mcp = FastMCP(
    "Gemini MCP Server",
    instructions="Provides access to Google's Gemini AI models for text generation, image analysis, and more."
)


def get_model(model_key: str):
    """Get or create a Gemini model instance"""
    if model_key not in model_instances:
        if model_key not in AVAILABLE_MODELS:
            model_key = settings.default_model
        model_instances[model_key] = genai.GenerativeModel(AVAILABLE_MODELS[model_key])
    return model_instances[model_key]


def call_with_memory(prompt: str, agent_name: str, temperature: float, model_key: str, tool_name: str, grounding: bool = False) -> str:
    """Handle memory-enabled call to Gemini model
    
    Args:
        prompt: User's prompt
        agent_name: Name of the agent for memory persistence
        temperature: Model temperature
        model_key: Model to use
        tool_name: Name of the calling tool
        grounding: Whether to use Google Search grounding
        
    Returns:
        AI model response with memory context
    """
    # Load agent's personality and conversation context
    agent_data = memory._load_agent(agent_name)
    personality = agent_data.get("personality", "")
    
    # Get recent conversation history for context
    context_messages = memory.get_context_for_llm(agent_name, last_n=10)
    
    # Build enhanced prompt with personality and context
    enhanced_prompt = ""
    if personality:
        enhanced_prompt += f"You are {agent_name}. {personality}\n\n"
    
    if context_messages:
        enhanced_prompt += "Here is our recent conversation history for context:\n\n"
        for msg in context_messages:
            role_prefix = "You" if msg["role"] == "assistant" else msg["role"].title()
            enhanced_prompt += f"{role_prefix}: {msg['content']}\n\n"
        
        enhanced_prompt += f"Current question: {prompt}"
    else:
        enhanced_prompt += prompt
    
    # Log user message to agent's memory
    try:
        memory.add_message(agent_name, "user", prompt, {
            "tool": tool_name,
            "model": model_key,
            "temperature": temperature
        })
    except IOError as e:
        raise IOError(f"Memory error: {e}")
    
    # Call the AI model with enhanced prompt
    try:
        if grounding:
            # Use genai_client for grounding with Google Search
            google_search_tool = Tool(google_search=GoogleSearch())
            
            response = genai_client.models.generate_content(
                model=AVAILABLE_MODELS[model_key],
                contents=enhanced_prompt,
                config=GenerateContentConfig(
                    tools=[google_search_tool],
                    response_modalities=["TEXT"],
                )
            )
            
            if response.candidates and response.candidates[0].content.parts:
                result_text = response.candidates[0].content.parts[0].text
            else:
                result_text = "No response generated"
        else:
            # Use standard GenerativeModel
            model_instance = get_model(model_key)
            
            response = model_instance.generate_content(
                enhanced_prompt,
                generation_config=genai.GenerationConfig(temperature=temperature)
            )
            result_text = response.text
        
        # Track usage
        input_tokens = estimate_tokens(enhanced_prompt)
        output_tokens = estimate_tokens(result_text)
        
        cost = usage_tracker.track_usage(
            provider="Gemini",
            model=AVAILABLE_MODELS[model_key],
            tool=tool_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            prompt=enhanced_prompt
        )
        
        # Log assistant response to agent's memory
        try:
            memory.add_message(agent_name, "assistant", result_text, {
                "tool": tool_name,
                "model": model_key,
                "temperature": temperature,
                "cost": cost,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens
            })
        except IOError as e:
            # Return result but note memory error
            raise IOError(f"AI response was generated, but saving to agent memory failed: {e}")
        
        return result_text
        
    except Exception as e:
        error_msg = f"Error calling Gemini: {str(e)}"
        # Log error to memory
        try:
            memory.add_message(agent_name, "assistant", error_msg, {
                "tool": tool_name,
                "model": model_key,
                "temperature": temperature,
                "error": True
            })
        except IOError:
            # If we can't log to memory, just return the original error
            pass
        raise ConnectionError(f"Error calling Gemini API: {e}")


@mcp.tool(
    name="ask",
    description="Asks a question to a Gemini model. Can analyze provided files, use Google Search for grounding, and maintain conversational context with a named agent. File handling: files parameter accepts a list where each item is a String (direct content), Dict with 'path' key (reads file), or Dict with 'content' key (uses provided content).",
    annotations=ToolAnnotations(
        title="Ask Gemini AI",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True
    )
)
def ask_gemini(
    prompt: str,
    agent_name: Optional[str] = None,
    model: str = "flash",
    temperature: float = 0.7,
    grounding: bool = False,
    files: Optional[List[Union[str, Dict[str, str]]]] = None
) -> str:
    """Ask Gemini a question with optional grounding (Google Search), memory support, and file analysis
    
    Args:
        prompt: The question or task to ask Gemini
        agent_name: Named agent for persistent conversation memory (e.g., 'testbot'). 
                   If provided, maintains context across conversations.
        model: Model to use (flash, pro, etc.)
        temperature: Response randomness (0.0-1.0)
        grounding: Use Google Search for real-time information
        files: Optional list of files to include in analysis. Each item can be:
               - String: direct content
               - Dict with 'path', 'content', and/or 'name' keys
    """
    
    if not gemini_available:
        raise RuntimeError(f"Gemini not available: {error_message}")
    
    # Process files if provided
    enhanced_prompt = prompt
    if files:
        try:
            normalized_files = normalize_file_inputs(files)
            file_contents = format_file_contents_for_llm(normalized_files)
            enhanced_prompt = f"{prompt}\n\n{file_contents}"
        except Exception as e:
            raise ValueError(f"Error processing files: {e}")
    
    # If agent_name is provided, use memory-enabled approach
    if agent_name:
        result = call_with_memory(enhanced_prompt, agent_name, temperature, model, "ask", grounding)
        
        # Just return the result for memory-enabled calls, usage is already tracked internally
        return result
    
    # Regular (no memory) approach
    try:
        if grounding:
            # Use genai_client for grounding with Google Search
            google_search_tool = Tool(google_search=GoogleSearch())
            
            response = genai_client.models.generate_content(
                model=AVAILABLE_MODELS[model],
                contents=enhanced_prompt,
                config=GenerateContentConfig(
                    tools=[google_search_tool],
                    response_modalities=["TEXT"],
                )
            )
            
            if response.candidates and response.candidates[0].content.parts:
                result_text = response.candidates[0].content.parts[0].text
            else:
                result_text = "No response generated"
        else:
            # Use standard GenerativeModel
            model_instance = get_model(model)
            
            response = model_instance.generate_content(
                enhanced_prompt,
                generation_config=genai.GenerationConfig(temperature=temperature)
            )
            result_text = response.text
        
        # Track usage
        input_tokens = estimate_tokens(enhanced_prompt)
        output_tokens = estimate_tokens(result_text)
        
        cost = usage_tracker.track_usage(
            provider="Gemini",
            model=AVAILABLE_MODELS[model],
            tool="ask",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            prompt=enhanced_prompt
        )
        
        # Add usage info
        usage_info = f"\n\n💰 Usage: {input_tokens + output_tokens} tokens (↑{input_tokens}/↓{output_tokens}) ≈${cost:.4f}"
        if grounding:
            usage_info += " [with search]"
        if files:
            usage_info += f" [with {len(files)} files]"
            
        return result_text + usage_info
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        raise ConnectionError(f"Error calling Gemini API: {e}")


@mcp.tool(
    name="analyze_image",
    description="Analyzes one or more images with a textual prompt using Gemini's vision model. Image handling: accepts images via image_data (single base64-encoded image string) or images (list of Dicts with 'path' key for local image files or 'data' key for base64-encoded images).",
    annotations=ToolAnnotations(
        title="Analyze Images with Gemini Vision",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True
    )
)
def analyze_image(
        prompt: str,
    image_data: Optional[str] = None,
    images: Optional[List[Dict[str, Any]]] = None,
    focus: str = "general",
    model: str = "pro",
    agent_name: Optional[str] = None
) -> str:
    """Analyze images using Gemini's vision capabilities"""
    
    if not gemini_available:
        raise RuntimeError(f"Gemini not available: {error_message}")
    
    try:
        # Handle image input - either single image_data or multiple images
        image_parts = []
        
        if images:
            for image in images:
                try:
                    if 'data' in image:
                        image_bytes = base64.b64decode(image['data'])
                        image_parts.append({
                            "mime_type": image.get('mime_type', 'image/jpeg'),
                            "data": image_bytes
                        })
                except Exception as e:
                    raise ValueError(f"Error processing image {image.get('name', 'unknown')}: {e}")
        
        elif image_data:
            try:
                # Handle data URL format
                if image_data.startswith('data:'):
                    header, data = image_data.split(',', 1)
                    mime_type = header.split(';')[0].replace('data:', '')
                    image_bytes = base64.b64decode(data)
                else:
                    # Assume it's raw base64
                    image_bytes = base64.b64decode(image_data)
                    mime_type = 'image/jpeg'
                
                image_parts.append({
                    "mime_type": mime_type,
                    "data": image_bytes
                })
            except Exception as e:
                raise ValueError(f"Error processing image data: {e}")
        
        else:
            raise ValueError("Either 'image_data' or 'images' parameter must be provided.")
        
        if not image_parts:
            raise ValueError("No valid image data was provided.")
        
        # Get enhanced prompt with focus
        if focus == "text":
            enhanced_prompt = f"Focus on extracting and analyzing any text content in the image(s). {prompt}"
        elif focus == "technical":
            enhanced_prompt = f"Provide a technical analysis focusing on diagrams, charts, code, or technical details. {prompt}"
        elif focus == "comparison":
            enhanced_prompt = f"Compare the images and analyze differences and similarities. {prompt}"
        else:
            enhanced_prompt = prompt
        
        # If agent_name is provided, use memory-enabled approach
        if agent_name:
            # Add conversation context to the prompt
            agent_data = mcp.memory._load_agent(agent_name)
            personality = agent_data.get("personality", "")
            context_messages = mcp.memory.get_context_for_llm(agent_name, last_n=5)
            
            if personality or context_messages:
                context_prompt = ""
                if personality:
                    context_prompt += f"You are {agent_name}. {personality}\n\n"
                
                if context_messages:
                    context_prompt += "Recent conversation context:\n"
                    for msg in context_messages[-3:]:  # Last 3 messages
                        role_prefix = "You" if msg["role"] == "assistant" else msg["role"].title()
                        content_preview = msg['content'][:100] + "..." if len(msg['content']) > 100 else msg['content']
                        context_prompt += f"{role_prefix}: {content_preview}\n"
                    context_prompt += "\n"
                
                enhanced_prompt = context_prompt + enhanced_prompt
            
            # Log user message to memory
            try:
                mcp.memory.add_message(agent_name, "user", f"Analyze image: {prompt}", {
                    "tool": "analyze_image",
                    "model": model,
                    "focus": focus
                })
            except IOError as e:
                raise IOError(f"Memory error: {e}")
        
        # Build content with prompt and images
        content = [enhanced_prompt] + image_parts
        
        # Get model and generate response
        model_instance = get_model(model)
        response = model_instance.generate_content(content)
        result_text = response.text
        
        # Track usage (estimate for image processing)
        input_tokens = estimate_tokens(enhanced_prompt) + 1000  # Rough estimate for image
        output_tokens = estimate_tokens(result_text)
        
        cost = usage_tracker.track_usage(
            provider="Gemini",
            model=AVAILABLE_MODELS[model],
            tool="analyze_image",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            prompt=enhanced_prompt
        )
        
        # If using memory, log the response
        if agent_name:
            try:
                mcp.memory.add_message(agent_name, "assistant", result_text, {
                    "tool": "analyze_image",
                    "model": model,
                    "cost": cost,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens
                })
            except IOError as e:
                # Return result but note memory error
                raise IOError(f"AI response was generated, but saving to agent memory failed: {e}")
        
        usage_info = f"\n\n💰 Usage: {input_tokens + output_tokens} tokens (↑{input_tokens}/↓{output_tokens}) ≈${cost:.4f} [with image]"
        
        return result_text + usage_info
        
    except Exception as e:
        raise RuntimeError(f"Error analyzing image with Gemini Vision: {e}")


@mcp.tool(
    name="generate_image",
    description="Generates an image from a text prompt using the Imagen model. Returns the path to the saved image file.",
    annotations=ToolAnnotations(
        title="Generate Images with Gemini",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True
    )
)
def generate_image(
        prompt: str,
    model: str = "image",
    agent_name: Optional[str] = None
) -> str:
    """Generate image using Imagen model"""
    
    if not gemini_available:
        raise RuntimeError(f"Gemini not available: {error_message}")
    
    try:
        if not hasattr(genai_client, 'models') or not genai_client:
            raise RuntimeError("Gemini client is not available for image generation.")
        
        # Map model keys
        image_models = {
            "image": "imagen-3.0-generate-002",
            "image-flash": "imagen-3.0-generate-002"
        }
        
        if model not in image_models:
            raise ValueError(f"Unknown image model '{model}'. Available: {list(image_models.keys())}")
        
        actual_model = image_models[model]
        
        # Generate image
        response = genai_client.models.generate_images(
            model=actual_model,
            prompt=prompt,
            config=GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio='1:1'
            )
        )
        
        result_parts = []
        
        # Process generated images
        for generated_image in response.generated_images:
            if generated_image.image and generated_image.image.image_bytes:
                # Save to temporary file
                import tempfile
                import uuid
                
                file_id = str(uuid.uuid4())[:8]
                filename = f"gemini_generated_{file_id}.png"
                filepath = os.path.join(tempfile.gettempdir(), filename)
                
                with open(filepath, 'wb') as f:
                    f.write(generated_image.image.image_bytes)
                
                result_parts.append(f"✅ **Image Generated Successfully**\n\n📁 **File:** `{filepath}`\n📏 **Size:** {len(generated_image.image.image_bytes):,} bytes")
        
        if not result_parts:
            raise RuntimeError("The API call succeeded but no image was generated.")
        
        result = "\n\n".join(result_parts)
        
        # Track cost
        cost = usage_tracker.track_usage(
            provider="Gemini",
            model=actual_model,
            tool="generate_image",
            input_tokens=estimate_tokens(prompt),
            output_tokens=0,
            prompt=prompt
        )
        
        result += f"\n\n💰 Cost: ≈${cost:.4f}"
        return result
        
    except Exception as e:
        raise RuntimeError(f"Error generating image with Imagen: {e}")


@mcp.tool(
    name="create_agent",
    description="Creates a new named agent to enable persistent conversation memory.",
    annotations=ToolAnnotations(
        title="Create Agent",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False
    )
)
def create_agent(
        agent_name: str,
    personality: Optional[str] = ""
) -> str:
    """Create a new named agent with optional personality"""
    if not agent_name:
        raise ValueError("Agent name is required.")
    
    try:
        created = memory.create_agent(agent_name, personality)
        
        if created:
            personality_text = f" with personality: '{personality}'" if personality else ""
            return f"✅ Agent '{agent_name}' created successfully{personality_text}!"
        else:
            raise ValueError(f"Agent '{agent_name}' already exists.")
    except IOError as e:
        raise IOError(f"Failed to create agent '{agent_name}': {e}")


@mcp.tool(
    name="list_agents",
    description="Lists all existing named agents and their summary statistics.",
    annotations=ToolAnnotations(
        title="List Agents",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False
    )
)
def list_agents() -> str:
    """List all available agents"""
    agents = memory.list_agents()
    
    if not agents:
        return f"📂 No agents found in {memory.memory_dir}\n\nUse 'create_agent' to create your first agent!"
    
    result = f"🤖 Found {len(agents)} agents:\n\n"
    
    for agent in agents:
        result += f"**{agent['name']}**\n"
        if agent['personality']:
            result += f"   🎭 Personality: {agent['personality']}\n"
        result += f"   📅 Created: {agent['created']}\n"
        result += f"   💬 Messages: {agent['message_count']}\n"
        result += f"   🎫 Tokens: {agent['total_tokens']:,}\n"
        result += f"   💰 Cost: ${agent['total_cost']:.4f}\n"
        result += f"   🕒 Last updated: {agent['last_updated']}\n\n"
    
    return result


@mcp.tool(
    name="agent_stats",
    description="Retrieves detailed statistics and conversation history for a specific named agent.",
    annotations=ToolAnnotations(
        title="Agent Statistics",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False
    )
)
def agent_stats(agent_name: str) -> str:
    """Get detailed statistics for a specific agent"""
    if not agent_name:
        raise ValueError("Agent name is required.")
    
    try:
        stats = memory.get_agent_stats(agent_name)
        
        result = f"## Agent '{stats['agent_name']}' Statistics\n\n"
        if stats['personality']:
            result += f"**🎭 Personality:** {stats['personality']}\n"
        result += f"**📅 Created:** {stats['created']}\n"
        result += f"**⏱️ Age:** {stats['agent_age']}\n"
        result += f"**💬 Total messages:** {stats['total_messages']}\n"
        result += f"   - User messages: {stats['user_messages']}\n"
        result += f"   - Assistant messages: {stats['assistant_messages']}\n"
        result += f"   - System messages: {stats['system_messages']}\n"
        result += f"**🎫 Total tokens:** {stats['total_tokens']:,}\n"
        result += f"**💰 Total cost:** ${stats['total_cost']:.4f}\n"
        result += f"**🕒 Last updated:** {stats['last_updated']}\n"
        result += f"**📂 Memory directory:** {stats['memory_dir']}\n"
        
        return result
    except FileNotFoundError:
        raise FileNotFoundError(f"Agent '{agent_name}' does not exist.")
    except Exception as e:
        raise RuntimeError(f"Error getting stats for agent '{agent_name}': {e}")


@mcp.tool(
    name="clear_agent",
    description="Clears the conversation history of a named agent, resetting its memory.",
    annotations=ToolAnnotations(
        title="Clear Agent History",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False
    )
)
def clear_agent(agent_name: str) -> str:
    """Clear an agent's conversation history"""
    if not agent_name:
        raise ValueError("Agent name is required.")
    
    try:
        cleared = memory.clear_agent(agent_name)
        
        if cleared:
            return f"✅ Agent '{agent_name}' conversation history cleared successfully!"
        else:
            return f"ℹ️ Agent '{agent_name}' already has empty conversation history"
    except IOError as e:
        raise IOError(f"Failed to clear agent '{agent_name}': {e}")


@mcp.tool(
    name="delete_agent",
    description="Permanently deletes a named agent and all of its associated data.",
    annotations=ToolAnnotations(
        title="Delete Agent",
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False
    )
)
def delete_agent(agent_name: str) -> str:
    """Delete an agent completely"""
    if not agent_name:
        raise ValueError("Agent name is required.")
    
    try:
        deleted = memory.delete_agent(agent_name)
        
        if deleted:
            return f"✅ Agent '{agent_name}' deleted permanently!"
        else:
            raise FileNotFoundError(f"Agent '{agent_name}' does not exist.")
    except IOError as e:
        raise IOError(f"Failed to delete agent '{agent_name}': {e}")


@mcp.tool(
    name="server_info",
    description="Checks the Gemini server status and API key configuration.",
    annotations=ToolAnnotations(
        title="Gemini Server Status",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False
    )
)
def server_info() -> str:
    """Get server status and configuration info"""
    if gemini_available:
        return f"""✅ **Gemini Server Available**

🔧 **Configuration:**
- Default Model: {settings.default_model}
- Available Models: {', '.join(AVAILABLE_MODELS.keys())}
- Temperature: {settings.default_temperature}

🛠️ **Available Tools:**
- ask: Text generation with optional Google Search grounding and memory support
- analyze_image: Image analysis and description with memory support
- generate_image: Image generation using Imagen
- create_agent: Create named agents with personalities
- list_agents: List all available agents
- agent_stats: Get detailed agent statistics
- clear_agent: Clear agent conversation history (keeps agent)
- delete_agent: Delete agent completely (permanent removal)
- server_info: This status information

💡 **Usage Tips:**
- Use grounding=true for real-time information, current events, or up-to-date knowledge
- Pro model recommended for complex analysis
- Flash model for faster responses"""
    else:
        return f"""❌ **Gemini Server Unavailable**

🔴 **Error:** {error_message}

🔧 **Setup Required:**
1. Set GEMINI_API_KEY environment variable
2. Install required dependencies: `pip install google-generativeai`
3. Restart the server

📚 **Get API Key:** https://makersuite.google.com/app/apikey"""


def main():
    """Main entry point"""
    # Run with stdio transport (synchronous)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
```

`mcp_handley_lab/llm/openai/README.md`:

```md
# OpenAI MCP Server

OpenAI GPT and DALL-E integration for Claude Code via Model Context Protocol.

## Quick Setup

1. **Get API Key**: [OpenAI Platform](https://platform.openai.com/api-keys)
2. **Set Environment Variable**: `export OPENAI_API_KEY="sk-your-key"`
3. **Install Dependencies**: `pip install -r requirements.txt`
4. **Register Server**: `claude config mcp add openai --scope user --command "python /path/to/openai/server.py"`

## OpenAI-Specific Features

### 🧠 **Reasoning Models**
- **o1-preview**: Advanced reasoning for complex problems
- **o1-mini**: Faster reasoning model
- Automatic parameter handling (no temperature, different token limits)

### 🎨 **DALL-E Integration**
- **DALL-E 3**: Latest model with HD quality and flexible aspect ratios
- **DALL-E 2**: Previous generation with cost-effective options
- Automatic size validation and parameter adjustment

### 🧮 **Enhanced Math Reasoner**
- Step-by-step mathematical problem solving
- Optimized for o1 reasoning models
- Configurable detail level with `show_work`

### ⚙️ **Flexible Parameters**
- **Temperature**: Full 0.0-2.0 range support
- **Max Tokens**: Configurable up to model limits
- **Model Selection**: Easy switching between all GPT models

## Available Tools

- **`ask_openai`** - Text generation with full parameter control
- **`openai_code_review`** - Code analysis with structured feedback
- **`openai_brainstorm`** - Creative ideation and problem-solving
- **`openai_generate_image`** - DALL-E image generation with quality controls
- **`openai_math_reasoner`** - Mathematical reasoning with o1 models

## Usage Examples

```python
# Standard question
ask_openai("Explain machine learning", model="gpt-4o", temperature=0.7)

# Reasoning model for complex problems
ask_openai("Design a distributed system", model="o1-preview")

# Code review with focus
openai_code_review(code="async def fetch_data():", focus="performance")

# High-quality image generation
openai_generate_image("Abstract digital art", model="dall-e-3", quality="hd", size="1792x1024")

# Mathematical problem solving
openai_math_reasoner("What is 15% of 240?", model="o1-preview", show_work=True)
```

## Models

### Chat Models
- `gpt-4o`: Latest GPT-4 optimized (default)
- `gpt-4o-mini`: Smaller, faster version
- `gpt-4-turbo`: Previous generation turbo
- `gpt-4`: Standard GPT-4
- `gpt-3.5-turbo`: Cost-effective option
- `o1-preview`: Advanced reasoning
- `o1-mini`: Faster reasoning

### Image Models
- `dall-e-3`: Latest with HD quality (default)
- `dall-e-2`: Previous generation

## Model-Specific Features

### Reasoning Models (o1-*)
- No temperature parameter (fixed internally)
- Uses `max_completion_tokens` instead of `max_tokens`
- Optimized for complex reasoning tasks
- Higher cost per token but superior reasoning

### DALL-E Models
- **DALL-E 3**: Supports HD quality, multiple aspect ratios
- **DALL-E 2**: Limited to square formats, standard quality
- Automatic parameter validation and adjustment

---

📚 **For complete documentation, setup instructions, and troubleshooting**, see the [main README](../README.md).
```

`mcp_handley_lab/llm/openai/requirements.txt`:

```txt
openai>=1.3.0
requests>=2.31.0
```

`mcp_handley_lab/llm/openai/server.py`:

```py
#!/usr/bin/env python3
"""
FastMCP-based OpenAI Server
Modern implementation using the official python-sdk
"""

import os
import base64
from typing import Dict, Any, List, Optional, Union

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic_settings import BaseSettings

# Import existing utilities we want to keep
from mcp_handley_lab.llm import (
    estimate_tokens, estimate_openai_tokens, usage_tracker, ModelDefaults
)
from mcp_handley_lab.llm.utils import normalize_file_inputs, format_file_contents_for_llm
from mcp_handley_lab.constants import PLACEHOLDER_API_KEY


class OpenAISettings(BaseSettings):
    """Settings for OpenAI server"""
    api_key: str = ""
    default_model: str = "gpt-4o"
    default_image_model: str = "dall-e-3"
    default_temperature: float = 0.7
    
    class Config:
        env_prefix = "OPENAI_"


# Available OpenAI models
AVAILABLE_MODELS = {
    # GPT-4o Series
    "gpt-4o": "gpt-4o",
    "gpt-4o-mini": "gpt-4o-mini",
    "gpt-4o-2024-11-20": "gpt-4o-2024-11-20",
    "gpt-4o-2024-08-06": "gpt-4o-2024-08-06",
    "gpt-4o-2024-05-13": "gpt-4o-2024-05-13",
    "gpt-4o-mini-2024-07-18": "gpt-4o-mini-2024-07-18",
    "gpt-4o-audio": "gpt-4o-audio-preview",
    "gpt-4o-mini-audio": "gpt-4o-mini-audio-preview",
    "chatgpt-4o": "chatgpt-4o-latest",
    
    # Legacy GPT-4
    "gpt-4-turbo": "gpt-4-turbo",
    "gpt-4": "gpt-4",
    
    # GPT-3.5 Series
    "gpt-3.5-turbo": "gpt-3.5-turbo",
    "gpt-3.5-turbo-instruct": "gpt-3.5-turbo-instruct",
    
    # O-Series Reasoning Models
    "o3": "o3",
    "o3-mini": "o3-mini",
    "o4-mini": "o4-mini",
    "o4-mini-high": "o4-mini-high",
    "o1": "o1",
    "o1-mini": "o1-mini",
    "o1-pro": "o1-pro",
    "o1-preview": "o1-preview",
}

# Image generation models
IMAGE_MODELS = {
    "gpt-image-1": "gpt-image-1",
    "dall-e-3": "dall-e-3",
    "dall-e-2": "dall-e-2",
}


# Initialize settings and client at module level
settings = OpenAISettings()

# Initialize OpenAI client
openai_available = False
error_message = ""
client = None

if not settings.api_key or settings.api_key == PLACEHOLDER_API_KEY:
    openai_available = False
    error_message = "Please set OPENAI_API_KEY environment variable"
else:
    try:
        import openai
        client = openai.OpenAI(api_key=settings.api_key)
        openai_available = True
        
    except Exception as e:
        openai_available = False
        error_message = str(e)


# Create FastMCP app
mcp = FastMCP(
    "OpenAI MCP Server",
    instructions="Provides access to OpenAI's GPT models for text generation, image analysis, and DALL-E for image generation."
)


@mcp.tool(
    name="ask",
    description="Asks a question to an OpenAI GPT model. Can analyze provided files for tasks like code review or document summarization. File handling: files parameter accepts a list where each item is a String (direct content), Dict with 'path' key (reads file), or Dict with 'content' key (uses provided content).",
    annotations=ToolAnnotations(
        title="Ask OpenAI GPT",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True
    )
)
def ask_openai(
    prompt: str,
    agent_name: Optional[str] = None,
    model: str = "gpt-4o",
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    files: Optional[List[Union[str, Dict[str, str]]]] = None
) -> str:
    """Ask OpenAI a question with optional file analysis
    
    Args:
        prompt: The question or task to ask OpenAI
        agent_name: Named agent for persistent conversation memory (not implemented yet)
        model: Model to use (gpt-4o, gpt-4, o1, etc.)
        temperature: Response randomness (0.0-1.0)
        max_tokens: Maximum tokens in response
        files: Optional list of files to include in analysis. Each item can be:
               - String: direct content
               - Dict with 'path', 'content', and/or 'name' keys
    """
    
    if not openai_available:
        raise RuntimeError(f"OpenAI not available: {error_message}")
    
    # Process files if provided
    enhanced_prompt = prompt
    if files:
        try:
            normalized_files = normalize_file_inputs(files)
            file_contents = format_file_contents_for_llm(normalized_files)
            enhanced_prompt = f"{prompt}\n\n{file_contents}"
        except Exception as e:
            raise ValueError(f"Error processing files: {e}")
    
    # Prepare API parameters
    api_params = {
        "model": AVAILABLE_MODELS.get(model, model),
        "messages": [{"role": "user", "content": enhanced_prompt}],
        "temperature": temperature
    }
    
    # Add max_tokens for non-o1 models (o1 models don't support max_tokens)
    if max_tokens and not model.startswith(("o1", "o3", "o4")):
        api_params["max_tokens"] = max_tokens
    
    try:
        response = client.chat.completions.create(**api_params)
        result_text = response.choices[0].message.content or ""
        
        # Track usage
        input_tokens = estimate_openai_tokens(enhanced_prompt, model)
        output_tokens = len(result_text.split()) * 1.3  # Rough estimate
        
        cost = usage_tracker.track_usage(
            provider="OpenAI",
            model=api_params["model"],
            tool="ask",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            prompt=enhanced_prompt
        )
        
        # Add usage info
        usage_info = f"\n\n💰 Usage: {input_tokens + output_tokens} tokens (↑{input_tokens}/↓{output_tokens}) ≈${cost:.4f}"
        if files:
            usage_info += f" [with {len(files)} files]"
            
        return result_text + usage_info
        
    except Exception as e:
        raise ConnectionError(f"Error calling OpenAI API: {e}")


@mcp.tool(
    name="analyze_image",
    description="Analyzes one or more images with a textual prompt using a GPT vision model. Image handling: accepts images via image_data (single base64-encoded image string) or images (list of Dicts with 'path' key for local image files or 'data' key for base64-encoded images).",
    annotations=ToolAnnotations(
        title="Analyze Images with GPT Vision",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True
    )
)
def analyze_image(
    prompt: str,
    image_data: Optional[str] = None,
    images: Optional[List[Dict[str, Any]]] = None,
    focus: str = "general",
    model: str = "gpt-4o",
    agent_name: Optional[str] = None
) -> str:
    """Analyze images using GPT's vision capabilities"""
    
    if not openai_available:
        raise RuntimeError(f"OpenAI not available: {error_message}")
    
    try:
        # Handle image input - either single image_data or multiple images
        message_content = [{"type": "text", "text": prompt}]
        
        if images:
            for image in images:
                try:
                    if 'data' in image:
                        # Base64 encoded image
                        image_url = f"data:image/jpeg;base64,{image['data']}"
                        message_content.append({
                            "type": "image_url",
                            "image_url": {"url": image_url}
                        })
                    elif 'path' in image:
                        # Read file and encode
                        with open(image['path'], 'rb') as f:
                            image_bytes = f.read()
                            image_b64 = base64.b64encode(image_bytes).decode()
                            image_url = f"data:image/jpeg;base64,{image_b64}"
                            message_content.append({
                                "type": "image_url", 
                                "image_url": {"url": image_url}
                            })
                except Exception as e:
                    raise ValueError(f"Error processing image {image.get('name', 'unknown')}: {e}")
        
        elif image_data:
            try:
                # Handle single image
                if image_data.startswith('data:'):
                    image_url = image_data
                else:
                    # Assume raw base64
                    image_url = f"data:image/jpeg;base64,{image_data}"
                
                message_content.append({
                    "type": "image_url",
                    "image_url": {"url": image_url}
                })
            except Exception as e:
                raise ValueError(f"Error processing image data: {e}")
        
        else:
            raise ValueError("Either 'image_data' or 'images' parameter must be provided.")
        
        # Call OpenAI Vision API
        response = client.chat.completions.create(
            model=AVAILABLE_MODELS.get(model, model),
            messages=[{"role": "user", "content": message_content}],
            max_tokens=1000
        )
        
        result_text = response.choices[0].message.content or ""
        
        # Track usage (estimate for image processing)
        input_tokens = estimate_openai_tokens(prompt, model) + 1000  # Rough estimate for image
        output_tokens = len(result_text.split()) * 1.3
        
        cost = usage_tracker.track_usage(
            provider="OpenAI",
            model=AVAILABLE_MODELS.get(model, model),
            tool="analyze_image",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            prompt=prompt
        )
        
        usage_info = f"\n\n💰 Usage: {input_tokens + output_tokens} tokens (↑{input_tokens}/↓{output_tokens}) ≈${cost:.4f} [with image]"
        
        return result_text + usage_info
        
    except Exception as e:
        raise RuntimeError(f"Error analyzing image with GPT Vision: {e}")


@mcp.tool(
    name="generate_image",
    description="Generates an image from a text prompt using a DALL-E model. Returns the path to the saved image file.",
    annotations=ToolAnnotations(
        title="Generate Images with DALL-E",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True
    )
)
def generate_image(
    prompt: str,
    model: str = "dall-e-3",
    quality: str = "standard",
    size: str = "1024x1024",
    agent_name: Optional[str] = None
) -> str:
    """Generate image using DALL-E model"""
    
    if not openai_available:
        raise RuntimeError(f"OpenAI not available: {error_message}")
    
    try:
        if model not in IMAGE_MODELS:
            raise ValueError(f"Unknown image model '{model}'. Available: {list(IMAGE_MODELS.keys())}")
        
        actual_model = IMAGE_MODELS[model]
        
        # Generate image
        response = client.images.generate(
            model=actual_model,
            prompt=prompt,
            size=size,
            quality=quality,
            n=1
        )
        
        # Save to temporary file
        import tempfile
        import uuid
        import requests
        
        file_id = str(uuid.uuid4())[:8]
        filename = f"openai_generated_{file_id}.png"
        filepath = os.path.join(tempfile.gettempdir(), filename)
        
        # Download and save the image
        image_url = response.data[0].url
        image_response = requests.get(image_url)
        image_response.raise_for_status()
        
        with open(filepath, 'wb') as f:
            f.write(image_response.content)
        
        result = f"✅ **Image Generated Successfully**\n\n📁 **File:** `{filepath}`\n📏 **Size:** {len(image_response.content):,} bytes"
        
        # Track cost
        cost = usage_tracker.track_usage(
            provider="OpenAI",
            model=actual_model,
            tool="generate_image",
            input_tokens=estimate_tokens(prompt),
            output_tokens=0,
            prompt=prompt
        )
        
        result += f"\n\n💰 Cost: ≈${cost:.4f}"
        return result
        
    except Exception as e:
        raise RuntimeError(f"Error generating image with DALL-E: {e}")


@mcp.tool(
    name="server_info",
    description="Checks the OpenAI server status and API key configuration.",
    annotations=ToolAnnotations(
        title="OpenAI Server Status",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False
    )
)
def server_info() -> str:
    """Get server status and configuration info"""
    if openai_available:
        return f"""✅ **OpenAI Server Available**

🔧 **Configuration:**
- Default Model: {settings.default_model}
- Default Image Model: {settings.default_image_model}
- Available Models: {', '.join(list(AVAILABLE_MODELS.keys())[:10])}... (+{len(AVAILABLE_MODELS)-10} more)
- Temperature: {settings.default_temperature}

🛠️ **Available Tools:**
- ask: Text generation and analysis with file support
- analyze_image: Image analysis using GPT Vision
- generate_image: Image generation using DALL-E
- server_info: This status information

💡 **Usage Tips:**
- Use o1/o3 models for complex reasoning tasks
- Use gpt-4o for general tasks with vision capabilities
- Use gpt-4o-mini for faster, cost-effective responses"""
    else:
        return f"""❌ **OpenAI Server Unavailable**

🔴 **Error:** {error_message}

🔧 **Setup Required:**
1. Set OPENAI_API_KEY environment variable
2. Install required dependencies: `pip install openai`
3. Restart the server

📚 **Get API Key:** https://platform.openai.com/api-keys"""


def main():
    """Main entry point"""
    # Run with stdio transport (synchronous)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
```

`mcp_handley_lab/llm/pricing.json`:

```json
{
  "gemini": {
    "gemini-2.5-flash-preview-05-20": {
      "input": 0.000075,
      "output": 0.0003
    },
    "gemini-2.5-pro-preview-06-05": {
      "input": 0.00125,
      "output": 0.005
    },
    "gemini-2.5-flash-preview-tts": {
      "input": 0.000075,
      "output": 0.0003
    },
    "gemini-2.5-pro-preview-tts": {
      "input": 0.00125,
      "output": 0.005
    },
    "gemini-2.0-flash-lite": {
      "input": 0.000075,
      "output": 0.0003
    },
    "imagen-3.0-generate-002": {
      "per_image": 0.04
    },
    "veo-2.0-generate-001": {
      "per_second": 0.1
    }
  },
  "openai": {
    "gpt-4.1": {
      "input": 0.0025,
      "output": 0.01
    },
    "gpt-4.1-mini": {
      "input": 0.00015,
      "output": 0.0006
    },
    "gpt-4.1-nano": {
      "input": 0.0001,
      "output": 0.0004
    },
    "gpt-4o": {
      "input": 0.0025,
      "output": 0.01
    },
    "gpt-4o-mini": {
      "input": 0.00015,
      "output": 0.0006
    },
    "gpt-4o-audio-preview": {
      "input": 0.0025,
      "output": 0.01
    },
    "gpt-4o-mini-audio-preview": {
      "input": 0.00015,
      "output": 0.0006
    },
    "chatgpt-4o-latest": {
      "input": 0.005,
      "output": 0.015
    },
    "gpt-4-turbo": {
      "input": 0.01,
      "output": 0.03
    },
    "gpt-4": {
      "input": 0.03,
      "output": 0.06
    },
    "gpt-3.5-turbo": {
      "input": 0.0005,
      "output": 0.0015
    },
    "gpt-3.5-turbo-instruct": {
      "input": 0.0015,
      "output": 0.002
    },
    "o3": {
      "input": 0.06,
      "output": 0.24
    },
    "o3-mini": {
      "input": 0.003,
      "output": 0.012
    },
    "o4-mini": {
      "input": 0.003,
      "output": 0.012
    },
    "o4-mini-high": {
      "input": 0.006,
      "output": 0.024
    },
    "o1": {
      "input": 0.015,
      "output": 0.06
    },
    "o1-mini": {
      "input": 0.003,
      "output": 0.012
    },
    "o1-pro": {
      "input": 0.06,
      "output": 0.24
    },
    "o1-preview": {
      "input": 0.015,
      "output": 0.06
    },
    "gpt-image-1": {
      "per_image_low": 0.01,
      "per_image_medium": 0.04,
      "per_image_high": 0.17,
      "per_image_default": 0.04
    },
    "dall-e-3": {
      "1024x1024": {"standard": 0.04, "hd": 0.08},
      "1792x1024": {"standard": 0.08, "hd": 0.12},
      "1024x1792": {"standard": 0.08, "hd": 0.12}
    },
    "dall-e-2": {
      "1024x1024": 0.02,
      "512x512": 0.018,
      "256x256": 0.016
    }
  }
}
```

`mcp_handley_lab/llm/requirements.txt`:

```txt
# Shared MCP utilities - no external dependencies required
# Individual servers may have their own requirements.txt files
```

`mcp_handley_lab/llm/schema_utils.py`:

```py
"""
Schema utility functions for generating common parameter definitions
"""
from typing import Dict, List, Any


def get_model_param(models: List[str], default: str) -> Dict[str, Any]:
    """Generate model parameter schema"""
    return {
        "type": "string",
        "description": f"Model to use: {models}",
        "default": default
    }


def get_files_param() -> Dict[str, Any]:
    """Generate files parameter schema"""
    return {
        "description": "Multiple files to include in the query (optional). Each item can be a string (content), or dict with 'path' and/or 'content'",
        "items": {
            "oneOf": [
                {"type": "string"},
                {
                    "type": "object",
                    "properties": {
                        "path": {"description": "File path", "type": "string"},
                        "content": {"description": "File content", "type": "string"},
                        "name": {"description": "Optional display name", "type": "string"}
                    }
                }
            ]
        },
        "type": "array"
    }


def get_focus_param() -> Dict[str, Any]:
    """Generate focus parameter schema"""
    return {
        "type": "string",
        "description": "Specific focus area (security, performance, etc.)",
        "default": "general"
    }


def get_temperature_param(default: float = 0.7) -> Dict[str, Any]:
    """Generate temperature parameter schema"""
    return {
        "type": "number",
        "description": "Temperature for response (0.0-2.0)",
        "default": default
    }


def get_path_param(description: str = "The absolute or relative path to the target directory") -> Dict[str, Any]:
    """Generate path parameter schema"""
    return {
        "type": "string",
        "description": description
    }


def get_include_param() -> Dict[str, Any]:
    """Generate include patterns parameter schema"""
    return {
        "type": "array",
        "items": {"type": "string"},
        "description": "Optional. An array of glob patterns (e.g., `['*.py', '*.js']`) to specify which files to include. If provided, only files matching these patterns will be processed.",
        "default": []
    }


def get_exclude_param() -> Dict[str, Any]:
    """Generate exclude patterns parameter schema"""
    return {
        "type": "array", 
        "items": {"type": "string"},
        "description": "Optional. An array of glob patterns (e.g., `['node_modules', '*.log']`) to exclude files and directories. Exclusions take precedence over inclusions.",
        "default": []
    }


def get_boolean_param(description: str, default: bool = False) -> Dict[str, Any]:
    """Generate boolean parameter schema"""
    return {
        "type": "boolean",
        "description": description,
        "default": default
    }


def get_enum_param(description: str, options: List[str], default: str = None) -> Dict[str, Any]:
    """Generate enum parameter schema"""
    schema = {
        "type": "string",
        "enum": options,
        "description": description
    }
    if default:
        schema["default"] = default
    return schema


def build_tool_schema(name: str, description: str, properties: Dict[str, Any], 
                     required: List[str] = None, title: str = None,
                     readOnlyHint: bool = False, destructiveHint: bool = False,
                     idempotentHint: bool = True, openWorldHint: bool = False) -> Dict[str, Any]:
    """Build complete tool schema with standard structure"""
    return {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "required": required or []
        },
        "annotations": {
            "title": title or name.replace("_", " ").title(),
            "readOnlyHint": readOnlyHint,
            "destructiveHint": destructiveHint,
            "idempotentHint": idempotentHint,
            "openWorldHint": openWorldHint
        }
    }
```

`mcp_handley_lab/llm/usage_tracker.py`:

```py
"""
Usage and cost tracking for MCP servers
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

# Load pricing data from external configuration
def _load_pricing_data() -> Dict[str, Dict[str, Dict[str, float]]]:
    """Load pricing data from external JSON file"""
    pricing_file = os.path.join(os.path.dirname(__file__), "pricing.json")
    try:
        with open(pricing_file, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        # Fallback to empty pricing if file not found or invalid
        print(f"Warning: Could not load pricing data from {pricing_file}: {e}")
        return {"gemini": {}, "openai": {}}

_PRICING_DATA = _load_pricing_data()
GEMINI_PRICING = _PRICING_DATA.get("gemini", {})
OPENAI_PRICING = _PRICING_DATA.get("openai", {})

@dataclass
class UsageEntry:
    timestamp: str
    provider: str
    model: str
    tool: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost: float
    prompt_preview: str

class UsageTracker:
    """Track token usage and costs for both Gemini and OpenAI"""
    
    def __init__(self, log_file: str = None):
        if log_file is None:
            # Get from config
            from mcp_handley_lab.llm.config import get_config
            config = get_config()
            log_file = config.usage_log_file or os.path.expanduser("~/.claude_mcp_usage.json")
        self.log_file = log_file
        
        # Cost calculation dispatch pattern
        self._cost_calculators = {
            "gemini": self._calculate_gemini_cost,
            "openai": self._calculate_openai_cost
        }
        
    def track_usage(self, 
                   provider: str, 
                   model: str, 
                   tool: str, 
                   input_tokens: int, 
                   output_tokens: int, 
                   prompt: str = "",
                   **kwargs) -> float:
        """Track usage and return estimated cost"""
        
        total_tokens = input_tokens + output_tokens
        cost = self._calculate_cost(provider, model, input_tokens, output_tokens, **kwargs)
        
        entry = UsageEntry(
            timestamp=datetime.now().isoformat(),
            provider=provider,
            model=model,
            tool=tool,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost=cost,
            prompt_preview=prompt[:100] + "..." if len(prompt) > 100 else prompt
        )
        
        self._log_usage(entry)
        return cost
    
    def _calculate_cost(self, provider: str, model: str, input_tokens: int, output_tokens: int, **kwargs) -> float:
        """Calculate estimated cost based on current pricing using dispatch pattern"""
        calculator = self._cost_calculators.get(provider.lower())
        return calculator(model, input_tokens, output_tokens, **kwargs) if calculator else 0.0
    
    def _calculate_gemini_cost(self, model: str, input_tokens: int, output_tokens: int, **kwargs) -> float:
        """Calculate Gemini-specific costs"""
        pricing = GEMINI_PRICING.get(model)
        if not pricing:
            return 0.0
        
        if "per_image" in pricing:
            return pricing["per_image"]
        elif "per_second" in pricing:
            return pricing["per_second"] * 10  # Estimate 10 seconds for video
        else:
            return (input_tokens / 1000) * pricing["input"] + (output_tokens / 1000) * pricing["output"]
    
    def _calculate_openai_cost(self, model: str, input_tokens: int, output_tokens: int, **kwargs) -> float:
        """Calculate OpenAI-specific costs"""
        pricing = OPENAI_PRICING.get(model)
        if not pricing:
            return 0.0
        
        if model.startswith("dall-e") or model == "gpt-image-1":
            return self._calculate_openai_image_cost(model, pricing, **kwargs)
        else:
            return (input_tokens / 1000) * pricing["input"] + (output_tokens / 1000) * pricing["output"]
    
    def _calculate_openai_image_cost(self, model: str, pricing: dict, **kwargs) -> float:
        """Calculate OpenAI image generation costs"""
        if model == "gpt-image-1":
            quality = kwargs.get("quality", "medium")
            return pricing.get(f"per_image_{quality}", pricing["per_image_default"])
        
        size = kwargs.get("size", "1024x1024")
        quality = kwargs.get("quality", "standard")
        
        if model == "dall-e-3":
            size_pricing = pricing.get(size, pricing["1024x1024"])
            return size_pricing.get(quality, size_pricing["standard"])
        else:  # dall-e-2
            return pricing.get(size, pricing["1024x1024"])
    
    def _log_usage(self, entry: UsageEntry):
        """Log usage entry to file"""
        try:
            # Read existing entries
            entries = []
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r') as f:
                    try:
                        data = json.load(f)
                        entries = data.get("usage_log", [])
                    except json.JSONDecodeError:
                        entries = []
            
            # Add new entry
            entries.append(asdict(entry))
            
            # Write back to file
            with open(self.log_file, 'w') as f:
                json.dump({"usage_log": entries}, f, indent=2)
                
        except Exception as e:
            # Don't fail the main operation if logging fails
            print(f"Warning: Could not log usage: {e}")
    
    def get_usage_summary(self, days: int = 30) -> Dict[str, Any]:
        """Get usage summary for the last N days"""
        if not os.path.exists(self.log_file):
            return {"total_cost": 0.0, "total_tokens": 0, "entries": []}
        
        try:
            with open(self.log_file, 'r') as f:
                data = json.load(f)
                entries = data.get("usage_log", [])
            
            # Filter by date
            from datetime import timedelta
            cutoff_date = datetime.now() - timedelta(days=days)
            
            recent_entries = []
            total_cost = 0.0
            total_input_tokens = 0
            total_output_tokens = 0
            total_tokens = 0
            provider_costs = {}
            model_usage = {}
            
            for entry in entries:
                entry_date = datetime.fromisoformat(entry["timestamp"])
                if entry_date >= cutoff_date:
                    recent_entries.append(entry)
                    total_cost += entry["estimated_cost"]
                    total_input_tokens += entry["input_tokens"]
                    total_output_tokens += entry["output_tokens"]
                    total_tokens += entry["total_tokens"]
                    
                    # Track by provider
                    provider = entry["provider"]
                    provider_costs[provider] = provider_costs.get(provider, 0.0) + entry["estimated_cost"]
                    
                    # Track by model
                    model = entry["model"]
                    if model not in model_usage:
                        model_usage[model] = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost": 0.0, "calls": 0}
                    model_usage[model]["input_tokens"] += entry["input_tokens"]
                    model_usage[model]["output_tokens"] += entry["output_tokens"]
                    model_usage[model]["total_tokens"] += entry["total_tokens"]
                    model_usage[model]["cost"] += entry["estimated_cost"]
                    model_usage[model]["calls"] += 1
            
            return {
                "period_days": days,
                "total_cost": round(total_cost, 4),
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
                "total_tokens": total_tokens,
                "total_calls": len(recent_entries),
                "provider_breakdown": {k: round(v, 4) for k, v in provider_costs.items()},
                "model_breakdown": {
                    k: {
                        "input_tokens": v["input_tokens"],
                        "output_tokens": v["output_tokens"],
                        "total_tokens": v["total_tokens"],
                        "cost": round(v["cost"], 4),
                        "calls": v["calls"]
                    } for k, v in model_usage.items()
                },
                "recent_entries": recent_entries[-10:]  # Last 10 entries
            }
            
        except Exception as e:
            return {"error": f"Could not read usage log: {e}"}

# Global tracker instance
usage_tracker = UsageTracker()

def estimate_tokens(text: str) -> int:
    """Rough token estimation (about 4 characters per token for English)"""
    from mcp_handley_lab.constants import TOKEN_ESTIMATION_DIVISOR
    return max(1, len(text) // TOKEN_ESTIMATION_DIVISOR)

def estimate_openai_tokens(text: str, model: str = "gpt-4o") -> int:
    """Accurate token counting for OpenAI models using tiktoken library"""
    import tiktoken
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        # Fallback to cl100k_base for unknown models (most GPT-4 models use this)
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))
```

`mcp_handley_lab/llm/utils.py`:

```py
"""
Shared utilities for MCP servers
"""

import json
import sys
import os
import base64
from typing import Dict, Any, List, Union, Optional


# Multi-file support utilities

class FileInput:
    """Represents a file input with content and metadata"""
    def __init__(self, path: str, content: str, name: Optional[str] = None):
        self.path = path
        self.content = content
        self.name = name or os.path.basename(path) if path else "unnamed"


def normalize_file_inputs(
    files: Union[str, List[str], List[Dict[str, str]], Dict[str, str]]
) -> List[FileInput]:
    """
    Normalize various file input formats to a list of FileInput objects.
    
    Accepts:
    - Single string (backward compatibility): treated as single file content
    - List of strings: treated as list of file contents
    - Single dict with 'path' and/or 'content'
    - List of dicts with 'path' and/or 'content'
    
    Returns:
    - List of FileInput objects
    """
    if isinstance(files, str):
        # Single string - backward compatibility
        return [FileInput(path="<inline>", content=files)]
    
    if isinstance(files, dict):
        # Single dict
        files = [files]
    
    normalized = []
    for i, file_data in enumerate(files):
        if isinstance(file_data, str):
            # String in list - treat as content
            normalized.append(FileInput(
                path=f"<inline-{i+1}>",
                content=file_data
            ))
        elif isinstance(file_data, dict):
            # Dict with path and/or content
            path = file_data.get('path', f"<inline-{i+1}>")
            content = file_data.get('content', '')
            name = file_data.get('name')
            
            # If path is provided but no content, try to read the file
            if path != f"<inline-{i+1}>" and not content:
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except Exception as e:
                    raise IOError(f"Error reading file '{path}': {e}")
            
            normalized.append(FileInput(path=path, content=content, name=name))
        else:
            # Raise exception for invalid input type
            raise TypeError(f"Invalid file input type at index {i}. Expected string or dict.")
    
    return normalized


def aggregate_file_contents(
    files: List[FileInput],
    separator: str = "\n\n" + "="*50 + "\n\n",
    include_headers: bool = True,
    max_files: Optional[int] = None,
    max_total_size: Optional[int] = None
) -> str:
    """
    Aggregate multiple file contents into a single string.
    
    Args:
        files: List of FileInput objects
        separator: String to separate files
        include_headers: Whether to include file headers
        max_files: Maximum number of files to include
        max_total_size: Maximum total size in characters
    
    Returns:
        Aggregated content string
    """
    if max_files and len(files) > max_files:
        files = files[:max_files]
    
    parts = []
    total_size = 0
    
    for file_input in files:
        if include_headers:
            header = f"File: {file_input.name} ({file_input.path})\n{'-'*50}\n"
            content = header + file_input.content
        else:
            content = file_input.content
        
        if max_total_size:
            # Estimate total size if we add this content
            separator_len = len(separator) if parts else 0
            estimated_total = total_size + separator_len + len(content)
            
            if estimated_total > max_total_size:
                # Calculate how much space is left
                available = max_total_size - total_size - separator_len
                if available <= 20:  # Need at least 20 chars for truncation message
                    break
                # Truncate content to fit
                content = content[:available-20] + "\n[Content truncated...]"
        
        parts.append(content)
        # Update total size for next iteration
        total_size += len(content)
        if parts:  # Now we have at least one part, so future additions need separator
            total_size += len(separator)
    
    return separator.join(parts)


def format_file_contents_simple(files: List[FileInput]) -> str:
    """Format file contents with simple headers for inline inclusion"""
    return "\n\n".join([
        f"## {file.name}\n{file.content}" 
        for file in files
    ])

def format_file_contents_for_llm(files: List[FileInput]) -> str:
    """Format file contents for LLM prompts with better structure and context"""
    parts = []
    for file in files:
        # Include full path and name, wrap content in code block for clarity
        parts.append(f"### File: `{file.name}` (Path: `{file.path}`)\n\n```\n{file.content}\n```")
    return "\n\n".join(parts)


def read_image_file(file_path: str) -> tuple[str, str]:
    """
    Read an image file and return base64 data and MIME type.
    
    Returns:
        Tuple of (base64_data, mime_type)
    """
    # Determine MIME type from extension
    ext = os.path.splitext(file_path)[1].lower()
    mime_types = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.bmp': 'image/bmp',
        '.webp': 'image/webp',
        '.svg': 'image/svg+xml'
    }
    mime_type = mime_types.get(ext, 'image/png')
    
    # Read and encode file
    with open(file_path, 'rb') as f:
        image_data = base64.b64encode(f.read()).decode('utf-8')
    
    return image_data, mime_type


def normalize_image_inputs(
    images: Union[str, List[str], List[Dict[str, str]], Dict[str, str]]
) -> List[Dict[str, str]]:
    """
    Normalize various image input formats to a list of image data dicts.
    
    Accepts:
    - Single string: file path or data URL
    - List of strings: file paths or data URLs
    - Single dict with 'path' or 'data'
    - List of dicts with 'path' or 'data'
    
    Returns:
    - List of dicts with 'data' (base64), 'mime_type', and 'name'
    """
    if isinstance(images, str):
        images = [images]
    elif isinstance(images, dict):
        images = [images]
    
    normalized = []
    for i, image_input in enumerate(images):
        if isinstance(image_input, str):
            if image_input.startswith('data:'):
                # Data URL
                parts = image_input.split(',', 1)
                if len(parts) == 2:
                    mime_type = parts[0].split(':')[1].split(';')[0]
                    data = parts[1]
                    name = f"image-{i+1}"
                else:
                    # Invalid data URL format - return error indicator
                    normalized.append({
                        'data': '',
                        'mime_type': 'image/png',
                        'name': f"error-image-{i+1}",
                        'error': f"Invalid data URL format: {image_input[:50]}..."
                    })
            else:
                # File path
                data, mime_type = read_image_file(image_input)
                name = os.path.basename(image_input)
            
            normalized.append({
                'data': data,
                'mime_type': mime_type,
                'name': name
            })
        elif isinstance(image_input, dict):
            if 'data' in image_input:
                # Already has data
                normalized.append({
                    'data': image_input['data'],
                    'mime_type': image_input.get('mime_type', 'image/png'),
                    'name': image_input.get('name', f"image-{i+1}")
                })
            elif 'path' in image_input:
                # Read from path
                data, mime_type = read_image_file(image_input['path'])
                normalized.append({
                    'data': data,
                    'mime_type': mime_type,
                    'name': image_input.get('name', os.path.basename(image_input['path']))
                })
            else:
                # Missing required keys - return error indicator
                normalized.append({
                    'data': '',
                    'mime_type': 'image/png',
                    'name': f"error-image-{i+1}",
                    'error': "Image dict must have either 'data' or 'path' key"
                })
        else:
            # Invalid input type - return error indicator
            normalized.append({
                'data': '',
                'mime_type': 'image/png',
                'name': f"error-image-{i+1}",
                'error': f"Invalid image input type: {type(image_input)}"
            })
    
    return normalized


def get_multi_image_analysis_prompt(
    images: List[Dict[str, str]], 
    prompt: str, 
    focus: str = "general"
) -> str:
    """Generate an image analysis prompt for multiple images"""
    intro = f"Please analyze these {len(images)} images"
    if focus != "general":
        intro += f" with a focus on {focus}"
    intro += ":\n\n"
    
    image_list = "Images included:\n"
    for i, image in enumerate(images, 1):
        image_list += f"{i}. {image['name']}\n"
    
    if focus == "comparison":
        return f"""{intro}{image_list}
**Question/Request:** {prompt}

**Required Output Format (Structured Markdown):**
Provide a comparative analysis using the following structure:

### 1. Individual Image Summaries
-   For each image ({image_list.strip()}), provide a brief summary of its main content and key elements relevant to the comparison.

### 2. Comparative Analysis
-   **Similarities**: Detail common elements, themes, styles, or characteristics across the images.
-   **Differences**: Highlight the distinctions, variations, or unique aspects of each image compared to the others.
-   **Trends/Patterns (Optional)**: If applicable, identify any overarching trends or patterns observable across the entire set.

### 3. Response to Specific Request
-   Directly and thoroughly address the original prompt: "{prompt}", synthesizing insights from the comparison.
-   Provide a concluding summary or recommendation based on your findings."""
    else:
        return f"""{intro}{image_list}
**Question/Request:** {prompt}

**Required Output Format (Structured Markdown):**
Provide your analysis in a well-structured Markdown format.

### 1. Individual Image Analysis
-   For each image listed above, provide a concise analysis focusing on:
    -   Main subjects and content.
    -   Relevant details addressing the request.
    -   Any text or readable content.
    -   Specific observations related to {focus if focus != 'general' else 'the question'}.

### 2. Overall Synthesis
-   Provide an overall analysis addressing the complete request, drawing insights from all images.
-   Summarize key findings or conclusions."""



def save_generated_image(image_bytes: bytes, provider_name: str) -> str:
    """Save generated image to file and return formatted success message
    
    Args:
        image_bytes: Raw image data as bytes
        provider_name: Name of the provider (e.g., "Gemini", "OpenAI")
    
    Returns:
        Formatted success message with file path and next steps
    """
    import time
    import os
    
    try:
        timestamp = int(time.time())
        filename = f"{provider_name.lower()}_image_{timestamp}.png"
        file_path = os.path.join(os.getcwd(), filename)
        
        with open(file_path, 'wb') as f:
            f.write(image_bytes)
            
        return (
            f"✅ Image Generation Successful!\n\n"
            f"- **Saved Locally To:** `{file_path}`\n\n"
            f"💡 **Next Steps:** You can now open this file directly from your system or reference it in other tools that accept local file paths for image analysis (e.g., `gemini:analyze_image` or `openai:analyze_image`)."
        )
    except Exception as save_error:
        # Fall back to base64 if file save fails
        import base64
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        return (
            f"⚠️ Image Generation Successful (Local Save Failed):\n\n"
            f"- **Local Save Error:** Could not save image to disk: {str(save_error)}\n"
            f"- **Base64 Data:** `data:image/png;base64,{image_base64[:60]}...` (truncated for display)\n\n"
            f"💡 **Next Steps:** The full base64 data is provided. You can paste this data URL directly into a web browser, an image viewer that supports data URLs, or pass it to other tools that accept base64 image data (e.g., `gemini:analyze_image` or `openai:analyze_image`)."
        )


def merge_messages_for_prompt(messages: List[Dict[str, str]]) -> str:
    """
    Merge system and user messages into a single prompt for models that don't support system role.
    Used by reasoning models (o1, o3) and Gemini which flatten message roles.
    """
    prompt_parts = []
    for msg in messages:
        role = msg["role"].capitalize()
        content = msg["content"]
        prompt_parts.append(f"{role}: {content}")
    
    return "\n\n".join(prompt_parts)


def merge_system_messages_for_api(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Merge system messages into user messages while preserving message structure for API calls.
    Used by OpenAI reasoning models that don't support system messages.
    """
    merged_messages = []
    system_content = ""
    
    for msg in messages:
        if msg["role"] == "system":
            system_content += msg["content"] + "\n\n"
        elif msg["role"] == "user":
            user_content = system_content + msg["content"] if system_content else msg["content"]
            merged_messages.append({"role": "user", "content": user_content})
            system_content = ""  # Reset for next user message
        else:
            merged_messages.append(msg)
    
    return merged_messages


```

`mcp_handley_lab/memory.py`:

```py
"""
Shared memory management for MCP servers
Stores conversation history across sessions for named agents
"""

import json
import os
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
import tempfile

class AgentMemory:
    """Manages conversation memory for multiple named agents"""
    
    def __init__(self, memory_dir: Optional[str] = None):
        """Initialize memory manager
        
        Args:
            memory_dir: Directory to store agent files (default: temp dir)
        """
        if memory_dir is None:
            memory_dir = os.path.join(tempfile.gettempdir(), "mcp_agent_memory")
        
        self.memory_dir = memory_dir
        os.makedirs(memory_dir, exist_ok=True)
        
        # Session memory for current conversation
        self.session_memory = {
            "session_id": str(int(time.time())),
            "session_start": datetime.now().isoformat(),
            "conversation_history": [],
            "total_cost": 0.0
        }
    
    def _get_agent_file(self, agent_name: str) -> str:
        """Get the file path for an agent's memory"""
        safe_name = "".join(c for c in agent_name if c.isalnum() or c in '-_').lower()
        return os.path.join(self.memory_dir, f"{safe_name}.json")
    
    def _load_agent(self, agent_name: str) -> Dict[str, Any]:
        """Load an agent's memory from file"""
        filepath = self._get_agent_file(agent_name)
        
        if not os.path.exists(filepath):
            # Create new agent
            return {
                "agent_name": agent_name,
                "created": datetime.now().isoformat(),
                "personality": "",
                "conversation_history": [],
                "total_tokens": 0,
                "total_cost": 0.0
            }
        
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception as e:
            # Memory should be resilient - return default agent data instead of failing
            # The calling tool handler will return error strings as needed
            return {
                "agent_name": agent_name,
                "created": datetime.now().isoformat(),
                "personality": "",
                "conversation_history": [],
                "total_tokens": 0,
                "total_cost": 0.0,
                "_load_error": str(e)  # Track the error for diagnostics
            }
    
    def _save_agent(self, agent_name: str, agent_data: Dict[str, Any]):
        """Save an agent's memory to file"""
        filepath = self._get_agent_file(agent_name)
        agent_data["last_updated"] = datetime.now().isoformat()
        
        try:
            with open(filepath, 'w') as f:
                json.dump(agent_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            raise IOError(f"Failed to save agent {agent_name}: {e}") from e
        
    def add_message(self, agent_name: str, role: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Add a message to an agent's conversation history
        
        Args:
            agent_name: Name of the agent
            role: 'user', 'assistant', or 'system'
            content: Message content
            metadata: Optional metadata (model, tool, cost, etc.)
        """
        agent_data = self._load_agent(agent_name)
        
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        agent_data["conversation_history"].append(message)
        
        # Update totals from metadata
        if metadata:
            agent_data["total_cost"] += metadata.get("cost", 0.0)
            agent_data["total_tokens"] += metadata.get("input_tokens", 0) + metadata.get("output_tokens", 0)
        
        self._save_agent(agent_name, agent_data)
    
    def get_conversation_history(self, agent_name: str, last_n: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get an agent's conversation history
        
        Args:
            agent_name: Name of the agent
            last_n: Return only last N messages (default: all)
            
        Returns:
            List of message dictionaries
        """
        agent_data = self._load_agent(agent_name)
        history = agent_data["conversation_history"]
        
        if last_n is None:
            return history.copy()
        return history[-last_n:] if last_n > 0 else []
    
    def get_context_for_llm(self, agent_name: str, last_n: Optional[int] = None, include_metadata: bool = False) -> List[Dict[str, str]]:
        """Get agent's conversation history formatted for LLM consumption
        
        Args:
            agent_name: Name of the agent
            last_n: Return only last N messages
            include_metadata: Whether to include metadata in content
            
        Returns:
            List of messages in LLM format (role, content)
        """
        history = self.get_conversation_history(agent_name, last_n)
        
        llm_messages = []
        for msg in history:
            content = msg["content"]
            
            # Optionally include metadata
            if include_metadata and msg.get("metadata"):
                metadata_str = json.dumps(msg["metadata"], indent=2)
                content += f"\n\n[Metadata: {metadata_str}]"
            
            llm_messages.append({
                "role": msg["role"],
                "content": content
            })
        
        return llm_messages
    
    def create_agent(self, agent_name: str, personality: str = "") -> bool:
        """Create a new agent with optional personality
        
        Args:
            agent_name: Name for the new agent
            personality: Optional personality/role description
            
        Returns:
            True if created, False if already exists
        """
        filepath = self._get_agent_file(agent_name)
        if os.path.exists(filepath):
            return False
        
        agent_data = {
            "agent_name": agent_name,
            "created": datetime.now().isoformat(),
            "personality": personality,
            "conversation_history": [],
            "total_tokens": 0,
            "total_cost": 0.0
        }
        
        self._save_agent(agent_name, agent_data)
        return True
    
    def list_agents(self) -> List[Dict[str, Any]]:
        """List all available agents
        
        Returns:
            List of agent info dictionaries
        """
        agents = []
        
        if not os.path.exists(self.memory_dir):
            return agents
        
        for filename in os.listdir(self.memory_dir):
            if filename.endswith('.json'):
                agent_name = filename[:-5]  # Remove .json extension
                try:
                    agent_data = self._load_agent(agent_name)
                    agents.append({
                        "name": agent_data["agent_name"],
                        "created": agent_data.get("created", "unknown"),
                        "personality": agent_data.get("personality", ""),
                        "message_count": len(agent_data["conversation_history"]),
                        "total_tokens": agent_data.get("total_tokens", 0),
                        "total_cost": agent_data.get("total_cost", 0.0),
                        "last_updated": agent_data.get("last_updated", "unknown")
                    })
                except Exception as e:
                    # Skip corrupted agent files but continue processing others
                    continue
        
        # Sort by last updated
        agents.sort(key=lambda x: x.get("last_updated", ""), reverse=True)
        return agents
    
    def search_messages(self, agent_name: str, query: str, case_sensitive: bool = False) -> List[Dict[str, Any]]:
        """Search an agent's messages containing query string
        
        Args:
            agent_name: Name of the agent to search
            query: Search term
            case_sensitive: Whether search is case sensitive
            
        Returns:
            List of matching messages
        """
        agent_data = self._load_agent(agent_name)
        history = agent_data["conversation_history"]
        
        if not case_sensitive:
            query = query.lower()
        
        matches = []
        for msg in history:
            content = msg["content"]
            if not case_sensitive:
                content = content.lower()
            
            if query in content:
                matches.append(msg)
        
        return matches
    
    def clear_agent(self, agent_name: str) -> bool:
        """Clear an agent's conversation history
        
        Args:
            agent_name: Name of the agent to clear
            
        Returns:
            True if cleared, False if agent doesn't exist
        """
        agent_data = self._load_agent(agent_name)
        if not agent_data["conversation_history"]:
            return False
        
        agent_data["conversation_history"] = []
        agent_data["total_tokens"] = 0
        agent_data["total_cost"] = 0.0
        self._save_agent(agent_name, agent_data)
        return True
    
    def delete_agent(self, agent_name: str) -> bool:
        """Delete an agent completely
        
        Args:
            agent_name: Name of the agent to delete
            
        Returns:
            True if deleted, False if agent doesn't exist
        """
        filepath = self._get_agent_file(agent_name)
        
        if not os.path.exists(filepath):
            return False
        
        try:
            os.remove(filepath)
            return True
        except Exception as e:
            # For delete operations, let the tool handler decide how to report errors
            raise IOError(f"Failed to delete agent {agent_name}: {e}") from e
    
    def get_agent_stats(self, agent_name: str) -> Dict[str, Any]:
        """Get statistics about an agent
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            Dictionary with agent statistics
            
        Raises:
            FileNotFoundError: If agent doesn't exist
        """
        filepath = self._get_agent_file(agent_name)
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Agent '{agent_name}' does not exist")
            
        agent_data = self._load_agent(agent_name)
        history = agent_data["conversation_history"]
        
        total_messages = len(history)
        user_messages = sum(1 for msg in history if msg["role"] == "user")
        assistant_messages = sum(1 for msg in history if msg["role"] == "assistant")
        system_messages = sum(1 for msg in history if msg["role"] == "system")
        
        # Parse creation date
        created_str = agent_data.get("created", "")
        if created_str:
            try:
                created = datetime.fromisoformat(created_str)
                agent_age = str(datetime.now() - created).split('.')[0]  # Remove microseconds
            except Exception:
                agent_age = "unknown"
        else:
            agent_age = "unknown"
        
        return {
            "agent_name": agent_data["agent_name"],
            "created": created_str,
            "agent_age": agent_age,
            "personality": agent_data.get("personality", ""),
            "total_messages": total_messages,
            "user_messages": user_messages,
            "assistant_messages": assistant_messages,
            "system_messages": system_messages,
            "total_tokens": agent_data.get("total_tokens", 0),
            "total_cost": agent_data.get("total_cost", 0.0),
            "last_updated": agent_data.get("last_updated", "unknown"),
            "memory_dir": self.memory_dir
        }
    
    def get_personality(self, agent_name: str) -> str:
        """Get an agent's personality/role description"""
        agent_data = self._load_agent(agent_name)
        return agent_data.get("personality", "")
    
    def set_personality(self, agent_name: str, personality: str):
        """Set an agent's personality/role description"""
        agent_data = self._load_agent(agent_name)
        agent_data["personality"] = personality
        self._save_agent(agent_name, agent_data)
```

`mcp_handley_lab/server.py`:

```py
"""
Base MCP server implementation with common protocol handling
"""

import json
import sys
import subprocess
import shutil
import time
import logging
import os
import yaml
import signal
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod

class MCPServer(ABC):
    """Base class for MCP servers with common protocol handling"""
    
    def __init__(self, name: str, version: str):
        self.name = name
        self.version = version
        self.error_count = 0
        self.max_errors = None  # No artificial limit
        self.last_error_time = 0
        self.error_reset_interval = None  # No artificial reset
        self.tool_schemas: Dict[str, Any] = {}
        self.tool_handlers: Dict[str, Any] = {}
        self._shutdown_requested = False
        self.error_message = ""  # For storing initialization and schema loading errors
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    @abstractmethod
    def get_tools(self) -> List[Dict[str, Any]]:
        """Return list of available tools"""
        pass
    
    @abstractmethod
    def handle_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Handle a specific tool call and return result"""
        pass

    def load_tool_schemas(self, schema_file: str) -> bool:
        """Load tool schemas from YAML file"""
        try:
            with open(schema_file, 'r') as f:
                self.tool_schemas = yaml.safe_load(f)['tools']
            return True
        except Exception as e:
            # Store error for later reporting instead of printing
            self.error_message = f"Could not load schemas from {schema_file}: {e}"
            return False
    
    
    def send_response(self, response: Dict[str, Any]):
        """Send a JSON-RPC response"""
        print(json.dumps(response), flush=True)
    
    def handle_initialize(self, request_id: Any) -> Dict[str, Any]:
        """Handle initialization request"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": self.name,
                    "version": self.version
                }
            }
        }
    
    def handle_tools_list(self, request_id: Any) -> Dict[str, Any]:
        """Handle tools list request"""
        tools = self.get_tools()
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": tools
            }
        }
    
    def handle_tool_call_request(self, request_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tool execution request"""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        try:
            result = self.handle_tool_call(tool_name, arguments)
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": result
                        }
                    ]
                }
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
    
    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a JSON-RPC request"""
        method = request.get("method")
        request_id = request.get("id")
        params = request.get("params", {})
        
        if method == "initialize":
            return self.handle_initialize(request_id)
        elif method == "tools/list":
            return self.handle_tools_list(request_id)
        elif method == "tools/call":
            return self.handle_tool_call_request(request_id, params)
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
    
    def reset_error_state(self):
        """Reset server error state - override in subclasses for specific cleanup"""
        pass
    
    def is_recoverable_error(self, error: Exception) -> bool:
        """Determine if an error is recoverable - override in subclasses"""
        # By default, most errors are considered recoverable
        return not isinstance(error, (SystemExit, KeyboardInterrupt))
    
    def handle_error(self, error: Exception, request: Dict[str, Any] = None) -> bool:
        """Handle an error and determine if server should continue"""
        current_time = time.time()
        
        # Reset error count if enough time has passed (if interval configured)
        if self.error_reset_interval and current_time - self.last_error_time > self.error_reset_interval:
            self.error_count = 0
        
        self.error_count += 1
        self.last_error_time = current_time
        
        # Send error response if we have a request ID
        if request and 'id' in request:
            self.send_response({
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(error)}"
                }
            })
        
        # If too many errors, attempt recovery (if limit configured)
        if self.max_errors and self.error_count >= self.max_errors:
            if self.is_recoverable_error(error):
                try:
                    self.reset_error_state()
                    self.error_count = 0
                    return True  # Continue running
                except Exception:
                    return False  # Give up
            else:
                return False  # Non-recoverable error
        
        return True  # Continue running
    
    def _signal_handler(self, signum, frame):
        """Handle system signals for graceful shutdown"""
        self._shutdown_requested = True
    
    def run(self):
        """Main server loop with improved error handling"""
        try:
            while True:
                # Check for shutdown request
                if self._shutdown_requested:
                    break
                    
                try:
                    line = sys.stdin.readline()
                    if not line:
                        break
                    
                    request = json.loads(line.strip())
                    response = self.handle_request(request)
                    self.send_response(response)
                    
                    # Reset error count on successful operation
                    if self.error_count > 0:
                        self.error_count = max(0, self.error_count - 1)
                    
                except json.JSONDecodeError:
                    continue
                except EOFError:
                    break
                except Exception as e:
                    should_continue = self.handle_error(e, locals().get('request'))
                    if not should_continue:
                        break
        except KeyboardInterrupt:
            # Graceful shutdown on Ctrl+C
            self._graceful_shutdown()
        except Exception as e:
            # Handle any other unexpected errors
            self._emergency_shutdown(e)
    
    def _graceful_shutdown(self):
        """Handle graceful shutdown"""
        try:
            # Send a final response if there's a pending request
            response = {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32000,
                    "message": "Server shutting down"
                },
                "id": None
            }
            self.send_response(response)
        except Exception:
            # If we can't send a response, just exit quietly
            pass
    
    def _emergency_shutdown(self, error: Exception):
        """Handle emergency shutdown due to unexpected error"""
        try:
            response = {
                "jsonrpc": "2.0", 
                "error": {
                    "code": -32603,
                    "message": f"Internal server error: {str(error)}"
                },
                "id": None
            }
            self.send_response(response)
        except Exception:
            # If we can't send a response, just exit
            pass

class APIServer(MCPServer):
    """Base class for API-based MCP servers (external services, APIs, etc.)"""
    
    def __init__(self, name: str, version: str, service_name: str):
        super().__init__(name, version)
        self.service_name = service_name
        self.available = False
        self.error_message = ""
        self.client = None
    
    @abstractmethod
    def _initialize_service(self):
        """Initialize the API service - must be implemented by subclasses"""
        pass
    
    def reset_error_state(self):
        """Reset API service state - reinitialize client if needed"""
        try:
            # Clear any cached state
            self.client = None
            self.available = False
            self.error_message = ""
            
            # Attempt to reinitialize
            self._initialize_service()
        except Exception as e:
            self.error_message = f"Service recovery failed: {str(e)}"
    
    def is_recoverable_error(self, error: Exception) -> bool:
        """API services can usually recover from common errors"""
        error_str = str(error).lower()
        recoverable_indicators = [
            'rate limit', 'quota', 'timeout', 'connection',
            'network', 'temporary', 'unavailable', 'busy',
            'authentication', 'credentials', 'token'
        ]
        
        return any(indicator in error_str for indicator in recoverable_indicators)


class CLICommandServer(MCPServer):
    """Base class for MCP servers that wrap CLI tools"""
    
    def __init__(self, name: str, version: str, cli_tool_name: str, display_name: str = None):
        super().__init__(name, version)
        self.cli_tool_name = cli_tool_name
        self.display_name = display_name or cli_tool_name
        self.available = self._check_cli_tool_available()
        self.error_message = "" if self.available else f"{self.cli_tool_name} CLI tool not found in PATH"
    
    def _check_cli_tool_available(self) -> bool:
        """Check if the CLI tool is available in PATH"""
        return shutil.which(self.cli_tool_name) is not None
    
    def get_server_info_tool(self) -> Dict[str, Any]:
        """Get server info tool for diagnostics"""
        return {
            "name": "server_info",
            "description": f"Get {self.display_name} server status and error information",
            "inputSchema": {
                "type": "object",
                "properties": {}
            },
            "annotations": {
                "title": f"{self.display_name} Server Info",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,  # Always returns same server status
                "openWorldHint": False  # Reads local server state
            }
        }
    
    def handle_server_info(self) -> str:
        """Handle server info request"""
        if self.available:
            try:
                result = subprocess.run([self.cli_tool_name, "--version"], capture_output=True, text=True)
                version = result.stdout.strip() if result.returncode == 0 else "unknown version"
                return f"✅ {self.display_name} MCP Server v{self.version} - {self.cli_tool_name} {version} available and ready!"
            except Exception as e:
                return f"✅ {self.display_name} MCP Server v{self.version} - {self.cli_tool_name} available but error getting version: {e}"
        else:
            return f"🔴 ERROR: {self.display_name} MCP Server v{self.version} - {self.cli_tool_name} not available. {self.error_message}"
    
    def _run_cli_command(self, cmd: List[str], capture_output: bool = True) -> tuple[bool, str]:
        """Run CLI command, returning (success, result_or_error_message)
        
        Args:
            cmd: Command to run as list of strings
            capture_output: Whether to capture stdout/stderr
            
        Returns:
            Tuple of (success: bool, result_or_error_message: str)
        """
        from mcp_handley_lab.constants import (
            MSG_CLI_COMMAND_FAILED, MSG_CLI_EXECUTION_FAILED, MSG_CLI_UNEXPECTED_ERROR,
            EMOJI_ERROR
        )
        
        try:
            result = subprocess.run(cmd, capture_output=capture_output, text=True)
            if result.returncode != 0:
                stderr = result.stderr.strip()
                error_msg = MSG_CLI_COMMAND_FAILED.format(
                    emoji=EMOJI_ERROR,
                    tool_name=self.display_name,
                    command=' '.join(cmd),
                    error=stderr if stderr else 'Unknown error'
                )
                return False, error_msg
            return True, result.stdout if capture_output else "SUCCESS"
        except subprocess.SubprocessError as e:
            error_msg = MSG_CLI_EXECUTION_FAILED.format(
                emoji=EMOJI_ERROR,
                tool_name=self.display_name,
                error=str(e)
            )
            return False, error_msg
        except Exception as e:
            error_msg = MSG_CLI_UNEXPECTED_ERROR.format(
                emoji=EMOJI_ERROR,
                tool_name=self.display_name,
                error=str(e)
            )
            return False, error_msg
    
    def build_cli_command(self, base_cmd: List[str], arguments: Dict[str, Any], arg_map: Dict[str, tuple]) -> List[str]:
        """Build CLI command using data-driven argument mapping
        
        Args:
            base_cmd: Base command as list (e.g., ["code2prompt", "path"])
            arguments: Dictionary of arguments from tool call
            arg_map: Mapping of {arg_name: (flag, type, default_value)}
                    where type is "bool", "value", or "list"
        
        Returns:
            Complete command list ready for subprocess.run
        """
        cmd = base_cmd.copy()
        
        for arg_name, arg_config in arg_map.items():
            value = arguments.get(arg_name)
            if value is None:
                continue
            
            flag, arg_type = arg_config[0], arg_config[1] 
            default = arg_config[2] if len(arg_config) > 2 else None
            
            if arg_type == "bool" and value:
                cmd.append(flag)
            elif arg_type == "value" and value != default:
                cmd.extend([flag, str(value)])
            elif arg_type == "list":
                for item in value:
                    cmd.extend([flag, item])
        
        return cmd
```

`mcp_handley_lab/tool_chainer/README.md`:

```md
# MCP Tool Chainer

A Model Context Protocol (MCP) server that enables chaining MCP tools together with result passing, placeholder replacement, and conditional execution.

## Features

- **Tool Discovery**: Automatically discover available tools from MCP servers
- **Tool Registration**: Register tools for use in chains
- **Sequential Execution**: Chain tools together with result passing
- **Placeholder Replacement**: Use `{PREV_RESULT}`, `{VARIABLE_NAME}` in tool arguments
- **Conditional Execution**: Skip steps based on conditions
- **File Output**: Save final results to files
- **Execution History**: Track chain executions with timing and statistics
- **Result Caching**: Cache intermediate results for efficiency

## Quick Start

### 1. Run the Tool Chainer Server

```bash
python -m mcp_handley_lab.tool_chainer.server
```

### 2. Discover Available Tools

```json
{
  "method": "tools/call",
  "params": {
    "name": "discover_tools",
    "arguments": {
      "server_command": "python -m mcp_handley_lab.llm.gemini.server"
    }
  }
}
```

### 3. Register Tools

```json
{
  "method": "tools/call",
  "params": {
    "name": "register_tool",
    "arguments": {
      "tool_id": "gemini_ask",
      "server_command": "python -m mcp_handley_lab.llm.gemini.server",
      "tool_name": "ask",
      "description": "Ask Gemini questions with grounding"
    }
  }
}
```

### 4. Define a Chain

```json
{
  "method": "tools/call",
  "params": {
    "name": "chain_tools",
    "arguments": {
      "chain_id": "research_chain",
      "steps": [
        {
          "tool_id": "gemini_ask",
          "arguments": {
            "prompt": "Research: {INITIAL_INPUT}",
            "grounding": true
          },
          "output_to": "RESEARCH_RESULT"
        },
        {
          "tool_id": "code2prompt_generate",
          "arguments": {
            "path": "/path/to/code",
            "include": ["*.py"]
          },
          "output_to": "CODE_SUMMARY"
        },
        {
          "tool_id": "gemini_ask",
          "arguments": {
            "prompt": "Analyze this code in context of: {RESEARCH_RESULT}\n\nCode: {CODE_SUMMARY}"
          }
        }
      ],
      "save_to_file": "/tmp/analysis_result.md"
    }
  }
}
```

### 5. Execute the Chain

```json
{
  "method": "tools/call",
  "params": {
    "name": "execute_chain",
    "arguments": {
      "chain_id": "research_chain",
      "initial_input": "modern authentication patterns in Python",
      "variables": {
        "PROJECT_NAME": "my-project"
      }
    }
  }
}
```

## Available Tools

### Tool Discovery

- **`discover_tools`**: Discover available tools from MCP servers
- **`register_tool`**: Register tools for use in chains

### Chain Management

- **`chain_tools`**: Define sequential tool chains
- **`execute_chain`**: Execute defined chains with result passing

### Utilities

- **`show_history`**: View execution history and statistics
- **`clear_cache`**: Clear cached results and history
- **`server_info`**: Get server status and registered tools

## Placeholder System

The tool chainer supports dynamic placeholder replacement in tool arguments:

### Built-in Placeholders

- `{INITIAL_INPUT}`: The initial input provided to the chain
- `{PREV_RESULT}`: Result from the previous step
- `{STEP_N_RESULT}`: Result from step N (e.g., `{STEP_1_RESULT}`)

### Custom Variables

- `{VARIABLE_NAME}`: Custom variables passed in `execute_chain`
- `{OUTPUT_VARIABLE}`: Variables set using `output_to` in steps

### Example Usage

```json
{
  "arguments": {
    "prompt": "Analyze {PREV_RESULT} in context of {PROJECT_TYPE}",
    "files": ["{CODE_PATH}/main.py"]
  }
}
```

## Conditional Execution

Steps can be executed conditionally based on previous results:

```json
{
  "tool_id": "error_handler",
  "arguments": {
    "error_log": "{PREV_RESULT}"
  },
  "condition": "{PREV_RESULT} contains error"
}
```

### Supported Conditions

- `{VAR} == "value"`: Exact string match
- `{VAR} != "value"`: Not equal
- `{VAR} contains "text"`: String contains text
- `{VAR}`: Truthy check (non-empty string)

## File Output

Chain results can be automatically saved to files:

```json
{
  "chain_id": "analysis",
  "steps": [...],
  "save_to_file": "/path/to/output.md"
}
```

## Integration Examples

### Code Analysis Pipeline

```json
{
  "chain_id": "code_analysis",
  "steps": [
    {
      "tool_id": "code2prompt",
      "arguments": {
        "path": "{PROJECT_PATH}",
        "include": ["*.py", "*.js"],
        "exclude": ["node_modules", "__pycache__"]
      },
      "output_to": "CODEBASE"
    },
    {
      "tool_id": "gemini_review",
      "arguments": {
        "code": "{CODEBASE}",
        "focus": "security"
      },
      "output_to": "SECURITY_REVIEW"
    },
    {
      "tool_id": "openai_ask",
      "arguments": {
        "prompt": "Create action items from: {SECURITY_REVIEW}",
        "model": "gpt-4"
      }
    }
  ]
}
```

### Research and Documentation

```json
{
  "chain_id": "research_doc",
  "steps": [
    {
      "tool_id": "gemini_research",
      "arguments": {
        "prompt": "Research latest trends in: {TOPIC}",
        "grounding": true
      },
      "output_to": "RESEARCH"
    },
    {
      "tool_id": "openai_ask",
      "arguments": {
        "prompt": "Create a technical blog post about {TOPIC} based on: {RESEARCH}",
        "model": "gpt-4"
      },
      "output_to": "BLOG_POST"
    },
    {
      "tool_id": "gemini_review",
      "arguments": {
        "document": "{BLOG_POST}",
        "focus": "technical accuracy"
      }
    }
  ],
  "save_to_file": "blog_post.md"
}
```

## Error Handling

- **Tool Failures**: Individual tool failures are captured and logged
- **Timeouts**: 30-second timeout per tool execution
- **Invalid Responses**: JSON parsing errors are handled gracefully
- **Missing Tools**: Validation ensures all referenced tools are registered

## Performance Features

- **Result Caching**: Intermediate results are cached for efficiency
- **Execution Timing**: Detailed timing statistics for each step
- **Memory Management**: Automatic cleanup of old execution history
- **Parallel Discovery**: Fast tool discovery with configurable timeouts

## Configuration

### Environment Variables

None required - the tool chainer works with standard library modules only.

### Server Configuration

Register with Claude Code:

```bash
claude config mcp add tool-chainer --scope user mcp-tool-chainer
```

## Best Practices

### Tool Registration

1. Use descriptive `tool_id` names
2. Include comprehensive descriptions
3. Specify appropriate `output_format`

### Chain Design

1. Keep chains focused and modular
2. Use meaningful variable names with `output_to`
3. Add conditions for error handling
4. Save important results to files

### Error Handling

1. Test individual tools before chaining
2. Use conditions to handle edge cases
3. Monitor execution history for performance issues

## Troubleshooting

### Common Issues

1. **Tool not found**: Ensure tools are registered before use
2. **Server timeout**: Check server command and availability
3. **Placeholder not replaced**: Verify variable names and spelling
4. **JSON errors**: Validate tool arguments format

### Debug Information

Use `show_history` to see detailed execution logs and `server_info` for current status.

## Integration with Claude Code

The tool chainer integrates seamlessly with Claude Code's MCP infrastructure:

```bash
# Discover Gemini tools
claude mcp call tool-chainer discover_tools --server_command "mcp-gemini"

# Register and chain tools
claude mcp call tool-chainer register_tool --tool_id gemini --server_command "mcp-gemini" --tool_name ask

# Execute complex workflows
claude mcp call tool-chainer execute_chain --chain_id my_workflow
```

This enables sophisticated AI workflows that combine multiple MCP servers and tools in a single, coordinated pipeline.
```

`mcp_handley_lab/tool_chainer/requirements.txt`:

```txt
mcp>=1.0.0
pydantic-settings>=2.0.0
```

`mcp_handley_lab/tool_chainer/server.py`:

```py
#!/usr/bin/env python3
"""
FastMCP-based Tool Chainer Server
Modern implementation using the official python-sdk
"""

import json
import re
import os
import sys
import subprocess
import tempfile
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic_settings import BaseSettings


class ToolChainerSettings(BaseSettings):
    """Settings for Tool Chainer server"""
    state_file: str = "~/.mcp_tool_chainer_state.json"
    
    class Config:
        env_prefix = "TOOL_CHAINER_"


# Initialize settings and state at module level
settings = ToolChainerSettings()
state_file = os.path.expanduser(settings.state_file)

# Initialize tool chainer state
registered_tools = {}
execution_history = []
result_cache = {}

# Load existing state if available
try:
    if os.path.exists(state_file):
        with open(state_file, 'r') as f:
            state = json.load(f)
            registered_tools = state.get("registered_tools", {})
            execution_history = state.get("execution_history", [])
            result_cache = state.get("result_cache", {})
except Exception as e:
    # Start with fresh state on error
    print(f"Warning: Could not load tool_chainer state: {e}", file=sys.stderr)
    registered_tools = {}
    execution_history = []
    result_cache = {}


# Create FastMCP app
mcp = FastMCP(
    "Tool Chainer MCP Server",
    instructions="Enables chaining MCP tools together with result passing and placeholder replacement. Supports sequential execution, parallel execution, and conditional execution."
)


def _save_state():
    """Helper to save the current state to file"""
    try:
        state = {
            "registered_tools": registered_tools,
            "execution_history": execution_history,
            "result_cache": result_cache
        }
        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        # Log error but don't crash the server
        print(f"Warning: Could not save tool_chainer state: {e}", file=sys.stderr)


def _auto_register_common_tools():
    """Auto-register common MCP tools if they're not already registered"""
    common_tools = [
        {
            "tool_id": "code2prompt",
            "server_command": "python -m mcp_handley_lab.code2prompt.server",
            "tool_name": "generate_prompt",
            "description": "Generate structured codebase summary",
            "output_format": "file_path"
        },
        {
            "tool_id": "gemini_ask",
            "server_command": "python -m mcp_handley_lab.llm.gemini.server",
            "tool_name": "ask",
            "description": "Ask Gemini questions"
        },
        {
            "tool_id": "gemini_review",
            "server_command": "python -m mcp_handley_lab.llm.gemini.server",
            "tool_name": "code_review",
            "description": "Analyze code with Gemini"
        },
        {
            "tool_id": "openai_ask",
            "server_command": "python -m mcp_handley_lab.llm.openai.server",
            "tool_name": "ask",
            "description": "Ask OpenAI questions"
        },
        {
            "tool_id": "openai_review",
            "server_command": "python -m mcp_handley_lab.llm.openai.server",
            "tool_name": "code_review",
            "description": "Analyze code with OpenAI"
        },
        {
            "tool_id": "jq_query",
            "server_command": "python -m mcp_handley_lab.jq.server",
            "tool_name": "query",
            "description": "Query JSON with jq"
        }
    ]
    
    registered_any = False
    for tool_config in common_tools:
        tool_id = tool_config["tool_id"]
        
        # Only register if not already registered
        if tool_id not in registered_tools:
            # Test if the server is available before registering
            if _test_server_availability(tool_config["server_command"]):
                registered_tools[tool_id] = {
                    "server_command": tool_config["server_command"],
                    "tool_name": tool_config["tool_name"],
                    "description": tool_config["description"],
                    "output_format": tool_config.get("output_format", "text"),
                    "registered_at": datetime.now().isoformat(),
                    "auto_registered": True
                }
                registered_any = True
    
    if registered_any:
        _save_state()


def _test_server_availability(server_command: str) -> bool:
    """Test if a server command is available and working"""
    try:
        # For FastMCP servers, need proper initialization sequence
        init_request = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "tool-chainer", "version": "1.0"}
            },
            "id": 1
        }
        
        initialized_notif = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        }
        
        tools_request = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 2
        }
        
        process = subprocess.Popen(
            server_command.split(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Send initialization sequence
        process.stdin.write(json.dumps(init_request) + '\n')
        process.stdin.flush()
        
        # Read init response
        response = process.stdout.readline()
        if not response:
            process.terminate()
            return False
        
        init_resp = json.loads(response)
        if 'error' in init_resp:
            process.terminate()
            return False
        
        # Send initialized notification
        process.stdin.write(json.dumps(initialized_notif) + '\n')
        process.stdin.flush()
        
        # Send tools/list request
        process.stdin.write(json.dumps(tools_request) + '\n')
        process.stdin.flush()
        
        # Read tools response
        response = process.stdout.readline()
        process.terminate()
        
        if response:
            tools_resp = json.loads(response)
            return "result" in tools_resp and "tools" in tools_resp["result"]
        
        return False
        
    except Exception:
        return False


def _replace_placeholders(text: str, variables: Dict[str, Any]) -> str:
    """Replace placeholders in text with variable values"""
    if not isinstance(text, str):
        return text
    
    # Replace {VAR_NAME} patterns
    for var_name, var_value in variables.items():
        placeholder = "{" + var_name + "}"
        if placeholder in text:
            text = text.replace(placeholder, str(var_value))
    
    return text


def _execute_tool(tool_id: str, arguments: Dict[str, Any], timeout: Optional[int] = None) -> Dict[str, Any]:
    """Execute a registered tool with given arguments"""
    if tool_id not in registered_tools:
        return {
            "success": False,
            "error": f"Tool '{tool_id}' is not registered"
        }
    
    tool_config = registered_tools[tool_id]
    server_command = tool_config["server_command"]
    tool_name = tool_config["tool_name"]
    
    try:
        # Prepare FastMCP request sequence
        init_request = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "tool-chainer", "version": "1.0"}
            },
            "id": 1
        }
        
        initialized_notif = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        }
        
        tool_request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            },
            "id": 2
        }
        
        process = subprocess.Popen(
            server_command.split(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Send initialization sequence
        process.stdin.write(json.dumps(init_request) + '\n')
        process.stdin.flush()
        
        # Read init response
        init_resp_line = process.stdout.readline()
        if not init_resp_line:
            process.terminate()
            return {"success": False, "error": "No response from server"}
        
        init_resp = json.loads(init_resp_line)
        if 'error' in init_resp:
            process.terminate()
            return {"success": False, "error": f"Initialization failed: {init_resp['error']}"}
        
        # Send initialized notification
        process.stdin.write(json.dumps(initialized_notif) + '\n')
        process.stdin.flush()
        
        # Send tool request
        process.stdin.write(json.dumps(tool_request) + '\n')
        process.stdin.flush()
        
        # Read tool response
        tool_resp_line = process.stdout.readline()
        process.terminate()
        
        if not tool_resp_line:
            return {"success": False, "error": "No response from tool call"}
        
        tool_resp = json.loads(tool_resp_line)
        
        if 'error' in tool_resp:
            return {
                "success": False,
                "error": tool_resp['error'].get('message', 'Unknown error'),
                "error_code": tool_resp['error'].get('code', -1)
            }
        
        # Extract result content
        result = tool_resp.get('result', {})
        if isinstance(result, dict) and 'content' in result:
            # FastMCP format
            content = result['content']
            if isinstance(content, list) and content:
                output = content[0].get('text', str(content))
            else:
                output = str(content)
        else:
            # Direct result
            output = str(result)
        
        return {
            "success": True,
            "output": output,
            "tool_id": tool_id,
            "tool_name": tool_name
        }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Tool execution timed out after {timeout} seconds"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Tool execution failed: {str(e)}"
        }


@mcp.tool(
    name="server_info",
    description="Shows the status of the tool chainer, including the number of registered tools and executed chains.",
    annotations=ToolAnnotations(
        title="Tool Chainer Server Status",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False
    )
)
def server_info() -> str:
    """Get server status and information"""
    num_tools = len(registered_tools)
    num_chains = len([h for h in execution_history if h.get('type') == 'chain'])
    
    return f"""⛓️ **Tool Chainer Server Status**

🔧 **Registered Tools:** {num_tools}
📊 **Executed Chains:** {num_chains}
🗃️ **State File:** {state_file}

**Available Commands:**
• discover_tools - Find tools from MCP servers
• register_tool - Register a tool for chaining
• chain_tools - Define a sequence of tool calls
• execute_chain - Run a defined chain
• clear_cache - Clear execution history and cache
• show_history - View recent executions

💡 **Usage:** Register tools from MCP servers, then chain them together for complex workflows!"""


@mcp.tool(
    name="discover_tools",
    description="Lists all available tools from a specified MCP server command.",
    annotations=ToolAnnotations(
        title="Discover MCP Server Tools",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False
    )
)
def discover_tools(
    server_command: Optional[str] = None,
    timeout: int = 5
) -> str:
    """Discover available tools from MCP servers"""
    if server_command:
        # Discover from specific server
        return _discover_from_server(server_command, timeout)
    else:
        # List all registered tools
        if not registered_tools:
            return "📭 **No tools registered yet**\n\n💡 Use `discover_tools` with a server_command to find available tools."
        
        tool_list = []
        for tool_id, config in registered_tools.items():
            desc = config.get('description', 'No description')
            server = config.get('server_command', 'Unknown server')
            tool_name = config.get('tool_name', 'Unknown tool')
            auto = " (auto)" if config.get('auto_registered') else ""
            
            tool_list.append(f"• **{tool_id}**{auto}")
            tool_list.append(f"  Tool: {tool_name}")
            tool_list.append(f"  Server: {server}")
            tool_list.append(f"  Description: {desc}")
            tool_list.append("")
        
        tools_text = '\n'.join(tool_list)
        
        return f"""🔧 **Registered Tools: {len(registered_tools)}**

{tools_text}

💡 **Usage:** Use these tool IDs in chain definitions."""


def _discover_from_server(server_command: str, timeout: int) -> str:
    """Discover tools from a specific server"""
    try:
        # FastMCP initialization sequence
        init_request = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "tool-chainer", "version": "1.0"}
            },
            "id": 1
        }
        
        initialized_notif = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        }
        
        tools_request = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 2
        }
        
        process = subprocess.Popen(
            server_command.split(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Send initialization
        process.stdin.write(json.dumps(init_request) + '\n')
        process.stdin.flush()
        
        # Read init response
        init_resp = json.loads(process.stdout.readline())
        if 'error' in init_resp:
            process.terminate()
            raise RuntimeError(f"Server initialization failed: {init_resp['error']}")
        
        # Send initialized notification
        process.stdin.write(json.dumps(initialized_notif) + '\n')
        process.stdin.flush()
        
        # Send tools request
        process.stdin.write(json.dumps(tools_request) + '\n')
        process.stdin.flush()
        
        # Read tools response
        tools_resp = json.loads(process.stdout.readline())
        process.terminate()
        
        if 'error' in tools_resp:
            raise RuntimeError(f"Tools discovery failed: {tools_resp['error']}")
        
        tools = tools_resp.get('result', {}).get('tools', [])
        
        if not tools:
            return f"📭 **No tools found in server**\n\n🔧 **Server:** {server_command}"
        
        tool_list = []
        for tool in tools:
            name = tool.get('name', 'Unknown')
            description = tool.get('description', 'No description')
            
            tool_list.append(f"• **{name}**")
            tool_list.append(f"  {description}")
            tool_list.append("")
        
        tools_text = '\n'.join(tool_list)
        
        return f"""🔧 **Tools Found: {len(tools)}**

**Server:** {server_command}

{tools_text}

💡 **Next:** Use `register_tool` to register any of these tools for chaining."""
        
    except Exception as e:
        raise RuntimeError(f"Failed to discover tools from server: {e}")


@mcp.tool(
    name="register_tool",
    description="Registers a specific tool from an MCP server, making it available for use in a chain.",
    annotations=ToolAnnotations(
        title="Register MCP Tool",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False
    )
)
def register_tool(
    tool_id: str,
    server_command: str,
    tool_name: str,
    description: str = "",
    output_format: str = "text",
    timeout: Optional[int] = None
) -> str:
    """Register a tool for chaining"""
    # Test server availability
    if not _test_server_availability(server_command):
        raise RuntimeError(f"Server command '{server_command}' is not available or not responding")
    
    # Register the tool
    tool_config = {
        "server_command": server_command,
        "tool_name": tool_name,
        "description": description or f"{tool_name} from {server_command}",
        "output_format": output_format,
        "timeout": timeout,
        "registered_at": datetime.now().isoformat(),
        "auto_registered": False
    }
    
    registered_tools[tool_id] = tool_config
    _save_state()
    
    return f"""✅ **Tool registered successfully: {tool_id}**

🔧 **Configuration:**
• Tool ID: {tool_id}
• Server: {server_command}
• Tool Name: {tool_name}
• Description: {tool_config['description']}
• Output Format: {output_format}
{f'• Timeout: {timeout}s' if timeout else '• Timeout: No limit'}

💡 **Next:** Use this tool_id in chain definitions!"""


def main():
    """Main entry point"""
    # Auto-register common tools after all functions are defined
    _auto_register_common_tools()
    
    # Run with stdio transport (synchronous)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
```

`mcp_handley_lab/tool_chainer/server_legacy.py`:

```py
#!/usr/bin/env python3
"""
MCP Tool Chainer Server

Enables chaining MCP tools together with result passing and placeholder replacement.
Supports sequential execution, parallel execution, and conditional execution.
"""

import json
import re
import sys
import os
import subprocess
import asyncio
import tempfile
import yaml
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from server import MCPServer
from utils import setup_unbuffered_io

setup_unbuffered_io()

class ToolChainer(MCPServer):
    """MCP server for chaining tools together with result passing"""
    
    def __init__(self):
        super().__init__("tool-chainer-mcp", "1.0.0")
        self.state_file = os.path.expanduser("~/.mcp_tool_chainer_state.json")
        self.tool_schemas = {}
        self.tool_handlers = {}
        self._load_tool_schemas()
        self._setup_dispatch_table()
        self._load_state()
        self._auto_register_common_tools()
    
    def _load_tool_schemas(self):
        """Load tool schemas from YAML file"""
        schema_file = os.path.join(os.path.dirname(__file__), 'schemas.yml')
        try:
            with open(schema_file, 'r') as f:
                self.tool_schemas = yaml.safe_load(f)['tools']
        except Exception as e:
            self.tool_schemas = {}
            print(f"Warning: Could not load schemas from {schema_file}: {e}")

    def _setup_dispatch_table(self):
        """Setup tool dispatch table"""
        self.tool_handlers = {
            "server_info": self._handle_server_info,
            "discover_tools": self._handle_discover_tools,
            "register_tool": self._handle_register_tool,
            "chain_tools": self._handle_chain_tools,
            "execute_chain": self._handle_execute_chain,
            "clear_cache": self._handle_clear_cache,
            "show_history": self._handle_show_history,
        }
        
    def _load_state(self):
        """Load persistent state from file"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    self.registered_tools = state.get("registered_tools", {})
                    self.execution_history = state.get("execution_history", [])
                    self.result_cache = state.get("result_cache", {})
            else:
                self.registered_tools = {}
                self.execution_history = []
                self.result_cache = {}
        except Exception:
            # If state file is corrupted, start fresh
            self.registered_tools = {}
            self.execution_history = []
            self.result_cache = {}
    
    def _save_state(self):
        """Save persistent state to file"""
        try:
            state = {
                "registered_tools": self.registered_tools,
                "execution_history": self.execution_history,
                "result_cache": self.result_cache
            }
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception:
            # Ignore save errors - continue without persistence
            pass
    
    def _auto_register_common_tools(self):
        """Auto-register common MCP tools if they're not already registered"""
        common_tools = [
            {
                "tool_id": "code2prompt",
                "server_command": "python -m mcp_handley_lab.code2prompt.server",
                "tool_name": "generate_prompt",
                "description": "Generate structured codebase summary",
                "output_format": "file_path"
            },
            {
                "tool_id": "gemini_ask",
                "server_command": "python -m mcp_handley_lab.llm.gemini.server",
                "tool_name": "ask",
                "description": "Ask Gemini questions"
            },
            {
                "tool_id": "gemini_review",
                "server_command": "python -m mcp_handley_lab.llm.gemini.server",
                "tool_name": "code_review",
                "description": "Analyze code with Gemini"
            },
            {
                "tool_id": "openai_ask",
                "server_command": "python -m mcp_handley_lab.llm.openai.server",
                "tool_name": "ask",
                "description": "Ask OpenAI questions"
            },
            {
                "tool_id": "openai_review",
                "server_command": "python -m mcp_handley_lab.llm.openai.server",
                "tool_name": "code_review",
                "description": "Analyze code with OpenAI"
            },
            {
                "tool_id": "jq_query",
                "server_command": "python -m mcp_handley_lab.jq.server",
                "tool_name": "query",
                "description": "Query JSON with jq"
            }
        ]
        
        registered_any = False
        for tool_config in common_tools:
            tool_id = tool_config["tool_id"]
            
            # Only register if not already registered
            if tool_id not in self.registered_tools:
                # Test if the server is available before registering
                if self._test_server_availability(tool_config["server_command"]):
                    self.registered_tools[tool_id] = {
                        "server_command": tool_config["server_command"],
                        "tool_name": tool_config["tool_name"],
                        "description": tool_config["description"],
                        "output_format": tool_config.get("output_format", "text"),
                        "registered_at": datetime.now().isoformat(),
                        "auto_registered": True
                    }
                    registered_any = True
        
        if registered_any:
            self._save_state()
    
    def _test_server_availability(self, server_command: str) -> bool:
        """Test if a server command is available and working"""
        try:
            request = {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": 1
            }
            
            process = subprocess.Popen(
                server_command.split(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate(
                input=json.dumps(request)
            )
            
            if process.returncode == 0:
                response = json.loads(stdout)
                return "result" in response and "tools" in response["result"]
            
            return False
            
        except Exception:
            return False
        
    def get_tools(self) -> List[Dict[str, Any]]:
        """Return available chaining tools"""
        available_tools = ['server_info', 'discover_tools', 'register_tool', 'chain_tools', 'execute_chain', 'clear_cache', 'show_history']
        return [self.tool_schemas.get(tool, {}) for tool in available_tools if tool in self.tool_schemas]
    
    def handle_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Handle tool execution requests"""
        handler = self.tool_handlers.get(tool_name)
        if not handler:
            raise ValueError(f"Unknown tool: '{tool_name}' is not recognized.")
        
        try:
            # server_info takes no arguments
            if tool_name == "server_info":
                return handler()
            return handler(arguments)
        except Exception as e:
            raise RuntimeError(f"Tool execution failed in '{tool_name}': {e}")
    
    def _handle_discover_tools(self, arguments: Dict[str, Any]) -> str:
        """Handle tool discovery requests"""
        server_command = arguments.get("server_command", "")
        
        if not server_command:
            raise ValueError("The 'server_command' argument is required.")
        
        try:
            # Send tools/list request to discover available tools
            request = {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": 1
            }
            
            process = subprocess.Popen(
                server_command.split(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate(
                input=json.dumps(request)
            )
            
            if process.returncode != 0:
                raise ConnectionError(f"Target server returned an error: {stderr}")
            
            response = json.loads(stdout)
            if "result" in response and "tools" in response["result"]:
                tools = response["result"]["tools"]
                result = f"✅ **Discovered {len(tools)} tools from server:**\n\n"
                
                for tool in tools:
                    name = tool.get("name", "unknown")
                    desc = tool.get("description", "No description")
                    result += f"- **{name}**: {desc}\n"
                
                result += f"\n**Registration command example:**\n"
                result += f"```json\n"
                result += f'{{\n  "tool_id": "my_{tools[0].get("name", "tool")}",\n'
                result += f'  "server_command": "{server_command}",\n'
                result += f'  "tool_name": "{tools[0].get("name", "tool")}",\n'
                result += f'  "description": "{tools[0].get("description", "")[:50]}..."\n'
                result += f"}}\n```"
                
                return result
            else:
                raise ValueError(f"Received an invalid response from the target server.")
                
        except subprocess.TimeoutExpired:
            raise TimeoutError("Discovery of tools from the target server timed out.")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON response from server: {e}")
        except Exception as e:
            raise RuntimeError(f"Tool discovery failed: {e}")
    
    def _handle_register_tool(self, arguments: Dict[str, Any]) -> str:
        """Register a tool for chaining"""
        tool_id = arguments.get("tool_id", "")
        server_command = arguments.get("server_command", "")
        tool_name = arguments.get("tool_name", "")
        description = arguments.get("description", "")
        output_format = arguments.get("output_format", "text")
        timeout = arguments.get("timeout")  # None if not specified
        
        if not all([tool_id, server_command, tool_name]):
            raise ValueError("The arguments 'tool_id', 'server_command', and 'tool_name' are all required.")
        
        tool_config = {
            "server_command": server_command,
            "tool_name": tool_name,
            "description": description,
            "output_format": output_format,
            "registered_at": datetime.now().isoformat()
        }
        
        if timeout is not None:
            tool_config["timeout"] = timeout
            
        self.registered_tools[tool_id] = tool_config
        self._save_state()
        
        return f"✅ **Tool registered successfully!**\n\n**ID:** {tool_id}\n**Tool:** {tool_name}\n**Description:** {description}\n**Server:** {server_command}"
    
    def _handle_chain_tools(self, arguments: Dict[str, Any]) -> str:
        """Define a tool chain"""
        chain_id = arguments.get("chain_id", "")
        steps = arguments.get("steps", [])
        save_to_file = arguments.get("save_to_file", "")
        
        if not chain_id or not steps:
            raise ValueError("The arguments 'chain_id' and 'steps' are required.")
        
        # Validate that all referenced tools are registered
        for i, step in enumerate(steps):
            tool_id = step.get("tool_id", "")
            if tool_id not in self.registered_tools:
                raise ValueError(f"Tool '{tool_id}' in step {i+1} is not registered. Please use 'register_tool' first.")
        
        chain_definition = {
            "steps": steps,
            "save_to_file": save_to_file,
            "created_at": datetime.now().isoformat()
        }
        
        # Store chain definition in result cache
        self.result_cache[f"chain_{chain_id}"] = chain_definition
        self._save_state()
        
        result = f"✅ **Chain '{chain_id}' defined successfully!**\n\n**Steps:**\n"
        for i, step in enumerate(steps):
            tool_id = step.get("tool_id", "")
            tool_info = self.registered_tools.get(tool_id, {})
            tool_name = tool_info.get("tool_name", tool_id)
            result += f"{i+1}. **{tool_name}** ({tool_id})\n"
            
            if step.get("condition"):
                result += f"   - Condition: `{step['condition']}`\n"
            if step.get("output_to"):
                result += f"   - Save to: `{step['output_to']}`\n"
        
        if save_to_file:
            result += f"\n**Final output will be saved to:** {save_to_file}"
        
        return result
    
    def _handle_execute_chain(self, arguments: Dict[str, Any]) -> str:
        """Execute a defined tool chain"""
        chain_id = arguments.get("chain_id", "")
        initial_input = arguments.get("initial_input", "")
        variables = arguments.get("variables", {})
        execution_timeout = arguments.get("timeout")  # Override timeout for this execution
        
        if not chain_id:
            raise ValueError("The 'chain_id' argument is required.")
        
        chain_key = f"chain_{chain_id}"
        if chain_key not in self.result_cache:
            raise ValueError(f"Chain '{chain_id}' not found. Please define it first with 'chain_tools'.")
        
        chain_definition = self.result_cache[chain_key]
        steps = chain_definition.get("steps", [])
        
        if not steps:
            raise ValueError(f"Chain '{chain_id}' has no steps defined.")
        
        # Initialize execution context
        context = {
            "INITIAL_INPUT": initial_input,
            "PREV_RESULT": initial_input,
            **variables
        }
        
        execution_log = []
        execution_start = datetime.now()
        
        try:
            for i, step in enumerate(steps):
                step_start = datetime.now()
                tool_id = step.get("tool_id", "")
                arguments_template = step.get("arguments", {})
                condition = step.get("condition", "")
                output_to = step.get("output_to", "")
                
                # Check condition if specified
                if condition and not self._evaluate_condition(condition, context):
                    execution_log.append({
                        "step": i + 1,
                        "tool_id": tool_id,
                        "status": "skipped",
                        "reason": f"Condition failed: {condition}"
                    })
                    continue
                
                # Replace placeholders in arguments
                resolved_arguments = self._replace_placeholders(arguments_template, context)
                
                # Execute the tool
                tool_info = self.registered_tools[tool_id]
                result = self._execute_tool(tool_info, resolved_arguments, execution_timeout)
                
                # Update context
                context["PREV_RESULT"] = result
                if output_to:
                    context[output_to] = result
                
                step_duration = (datetime.now() - step_start).total_seconds()
                
                execution_log.append({
                    "step": i + 1,
                    "tool_id": tool_id,
                    "tool_name": tool_info.get("tool_name", tool_id),
                    "status": "completed",
                    "duration_seconds": step_duration,
                    "result_length": len(str(result))
                })
            
            final_result = context.get("PREV_RESULT", "")
            
            # Save to file if specified
            save_to_file = chain_definition.get("save_to_file", "")
            if save_to_file:
                try:
                    with open(save_to_file, 'w') as f:
                        f.write(str(final_result))
                    execution_log.append({
                        "step": "file_save",
                        "status": "completed",
                        "file_path": save_to_file
                    })
                except Exception as e:
                    execution_log.append({
                        "step": "file_save",
                        "status": "failed",
                        "error": str(e)
                    })
            
            # Store execution history
            total_duration = (datetime.now() - execution_start).total_seconds()
            self.execution_history.append({
                "chain_id": chain_id,
                "executed_at": execution_start.isoformat(),
                "total_duration_seconds": total_duration,
                "steps_executed": len([log for log in execution_log if log.get("status") == "completed"]),
                "final_result_length": len(str(final_result)),
                "log": execution_log
            })
            self._save_state()
            
            # Format response
            response = f"✅ **Chain '{chain_id}' executed successfully!**\n\n"
            response += f"**Execution Summary:**\n"
            response += f"- Duration: {total_duration:.2f} seconds\n"
            response += f"- Steps completed: {len([log for log in execution_log if log.get('status') == 'completed'])}/{len(steps)}\n\n"
            
            response += f"**Steps:**\n"
            for log_entry in execution_log:
                step_num = log_entry.get("step", "?")
                status = log_entry.get("status", "unknown")
                tool_name = log_entry.get("tool_name", log_entry.get("tool_id", ""))
                
                if status == "completed":
                    duration = log_entry.get("duration_seconds", 0)
                    result_len = log_entry.get("result_length", 0)
                    response += f"{step_num}. ✅ {tool_name} ({duration:.2f}s, {result_len} chars)\n"
                elif status == "skipped":
                    reason = log_entry.get("reason", "")
                    response += f"{step_num}. ⏭️ {tool_name} - {reason}\n"
                elif status == "failed":
                    error = log_entry.get("error", "")
                    response += f"{step_num}. ❌ {tool_name} - {error}\n"
            
            if save_to_file:
                response += f"\n**Output saved to:** {save_to_file}\n"
            
            response += f"\n**Final Result:**\n```\n{str(final_result)[:1000]}{'...' if len(str(final_result)) > 1000 else ''}\n```"
            
            return response
            
        except Exception as e:
            raise RuntimeError(f"Chain execution failed: {e}")
    
    def _handle_clear_cache(self, arguments: Dict[str, Any]) -> str:
        """Clear cached results and execution history"""
        self.result_cache.clear()
        self.execution_history.clear()
        self._save_state()
        return "✅ Cache and execution history cleared"
    
    def _handle_show_history(self, arguments: Dict[str, Any]) -> str:
        """Show execution history"""
        limit = arguments.get("limit", 10)
        
        if not self.execution_history:
            return "📝 No execution history available"
        
        recent_history = self.execution_history[-limit:]
        
        result = f"📜 **Execution History (last {len(recent_history)} entries):**\n\n"
        
        for entry in reversed(recent_history):
            chain_id = entry.get("chain_id", "unknown")
            executed_at = entry.get("executed_at", "")
            duration = entry.get("total_duration_seconds", 0)
            steps = entry.get("steps_executed", 0)
            
            result += f"**{chain_id}** - {executed_at[:19]}\n"
            result += f"  Duration: {duration:.2f}s, Steps: {steps}\n\n"
        
        result += f"**Registered Tools:** {len(self.registered_tools)}\n"
        result += f"**Cached Results:** {len(self.result_cache)}\n"
        
        return result
    
    def _handle_server_info(self) -> str:
        """Handle server info request"""
        result = f"✅ **Tool Chainer MCP Server v{self.version}**\n\n"
        result += f"**Status:** Running and ready\n"
        result += f"**Registered Tools:** {len(self.registered_tools)}\n"
        result += f"**Execution History:** {len(self.execution_history)} chains executed\n"
        result += f"**Cached Results:** {len(self.result_cache)} items\n\n"
        
        if self.registered_tools:
            result += "**Registered Tools:**\n"
            for tool_id, tool_info in self.registered_tools.items():
                result += f"- `{tool_id}`: {tool_info.get('tool_name', '')} - {tool_info.get('description', '')[:50]}...\n"
        
        return result
    
    def _replace_placeholders(self, template: Any, context: Dict[str, Any]) -> Any:
        """Replace placeholders in arguments using context"""
        if isinstance(template, str):
            # Replace placeholders like {PREV_RESULT}, {VARIABLE_NAME}
            result = template
            for key, value in context.items():
                placeholder = f"{{{key}}}"
                if placeholder in result:
                    result = result.replace(placeholder, str(value))
            return result
        elif isinstance(template, dict):
            return {k: self._replace_placeholders(v, context) for k, v in template.items()}
        elif isinstance(template, list):
            return [self._replace_placeholders(item, context) for item in template]
        else:
            return template
    
    def _evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """Evaluate a simple condition string"""
        # Simple condition evaluation - could be expanded
        # Supports: {VAR} == "value", {VAR} != "value", {VAR} contains "text"
        
        # Replace placeholders first
        resolved_condition = self._replace_placeholders(condition, context)
        
        # Simple string conditions
        if " == " in resolved_condition:
            left, right = resolved_condition.split(" == ", 1)
            return left.strip().strip('"') == right.strip().strip('"')
        elif " != " in resolved_condition:
            left, right = resolved_condition.split(" != ", 1)
            return left.strip().strip('"') != right.strip().strip('"')
        elif " contains " in resolved_condition:
            left, right = resolved_condition.split(" contains ", 1)
            return right.strip().strip('"') in left.strip().strip('"')
        else:
            # Treat as boolean - non-empty strings are True
            return bool(resolved_condition.strip())
    
    def _execute_tool(self, tool_info: Dict[str, Any], arguments: Dict[str, Any], execution_timeout: Optional[float] = None) -> str:
        """Execute a registered tool with given arguments"""
        server_command = tool_info["server_command"]
        tool_name = tool_info["tool_name"]
        
        # Create tool call request
        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            },
            "id": 1
        }
        
        try:
            process = subprocess.Popen(
                server_command.split(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Determine timeout: execution override > tool-specific > no timeout
            timeout = execution_timeout or tool_info.get("timeout")
            
            stdout, stderr = process.communicate(
                input=json.dumps(request),
                timeout=timeout
            )
            
            if process.returncode != 0:
                raise Exception(f"Server error: {stderr}")
            
            response = json.loads(stdout)
            
            if "result" in response:
                result = response["result"]
                if isinstance(result, dict) and "content" in result:
                    # Extract text content from MCP response format
                    content = result["content"]
                    if isinstance(content, list) and len(content) > 0:
                        return content[0].get("text", str(content))
                    else:
                        return str(content)
                else:
                    return str(result)
            elif "error" in response:
                raise Exception(f"Tool error: {response['error']}")
            else:
                raise Exception(f"Invalid response: {response}")
                
        except subprocess.TimeoutExpired:
            raise Exception("Tool execution timed out")
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON response: {e}")
        except Exception as e:
            raise Exception(f"Tool execution failed: {e}")

def main():
    server = ToolChainer()
    server.run()

if __name__ == "__main__":
    main()
```

`mcp_handley_lab/utils.py`:

```py
"""
Core MCP protocol utilities
"""

import sys

def setup_unbuffered_io():
    """Configure stdin/stdout for MCP communication"""
    # Force line buffering for stdin/stdout
    # Skip if running in pytest (stdin is a special object)
    if hasattr(sys.stdin, 'reconfigure'):
        sys.stdin.reconfigure(line_buffering=True)
        sys.stdout.reconfigure(line_buffering=True)
        sys.stderr.reconfigure(line_buffering=True)

def format_error(message: str, error_code: str = None) -> str:
    """Standardize error message formatting across all servers"""
    prefix = f"[{error_code}] " if error_code else "[ERROR] "
    return f"🔴 {prefix}{message}"
```

`mcp_handley_lab/vim/README.md`:

```md
# Vim MCP Server

Interactive text editing using vim through the Model Context Protocol. This server allows Claude to prompt users for interactive edits to content like emails, commit messages, prompts, and documents using their preferred vim editor.

## Overview

The Vim MCP server enables a git-style EDITOR workflow where Claude can:
1. Draft initial content (emails, commit messages, etc.)
2. Open vim for user refinement 
3. Track and analyze the changes made by the user
4. Continue the conversation with knowledge of user modifications

This is particularly useful for collaborative writing, email composition, commit message crafting, and document editing where human creativity and Claude's assistance can be combined effectively.

## Features

- **Interactive Editing**: Opens vim with pre-populated content for user editing
- **Change Tracking**: Automatically detects and summarizes user modifications
- **Multi-Environment Support**: Works with TTY, tmux sessions, and terminal emulators
- **File Type Awareness**: Provides appropriate syntax highlighting and commenting
- **Diff Generation**: Shows detailed before/after comparisons
- **Temporary File Management**: Secure handling of temporary editing files

## Tools

### `prompt_user_edit`

Opens vim with content for interactive editing and returns a summary of changes made.

**Parameters:**
- `content` (required): Initial text content to edit
- `file_extension` (optional): File extension for syntax highlighting (default: `.txt`)
- `instructions` (optional): Instructions to display as comments in the file
- `show_diff` (optional): Whether to include detailed diff in response (default: `true`)
- `keep_file` (optional): Whether to preserve the temporary file after editing (default: `false`)

**Example:**
```json
{
  "name": "prompt_user_edit",
  "arguments": {
    "content": "Draft email content here...",
    "file_extension": ".md",
    "instructions": "Please refine this email for clarity and tone",
    "show_diff": true
  }
}
```

### `quick_edit`

Simplified editing interface that opens vim with minimal setup for quick content creation.

**Parameters:**
- `file_extension` (optional): File extension for syntax highlighting (default: `.txt`)
- `instructions` (optional): Instructions for the editing task
- `initial_content` (optional): Starting content (default: empty)

**Example:**
```json
{
  "name": "quick_edit",
  "arguments": {
    "file_extension": ".py",
    "instructions": "Create a simple Python script"
  }
}
```

## Installation & Setup

### Prerequisites

- **vim**: Must be installed and available in PATH
- **Python 3.8+**: Required for the MCP server
- **Terminal Environment**: TTY access, tmux, or terminal emulator support

### Installation

```bash
# Install the package
pip install mcp-handley-lab

# Register with Claude Code
claude config mcp add vim-server mcp_handley_lab.vim.server --scope user
```

### Configuration

Add to your Claude Code MCP configuration:

```json
{
  "mcp": {
    "servers": {
      "vim": {
        "command": "python",
        "args": ["-m", "mcp_handley_lab.vim.server"],
        "env": {}
      }
    }
  }
}
```

## Environment Support

The server automatically detects and adapts to different environments:

### 1. TTY Environment (Direct)
When run in a terminal with TTY access, vim opens directly:
```bash
# Works in standard terminal sessions
vim /tmp/mcp_edit_abc123.txt
```

### 2. tmux Integration  
When running inside tmux, creates a new adjacent window:
```bash
# Creates new window: "vim→[parent-window]"
tmux new-window -a -n "vim→claude" vim /tmp/mcp_edit_abc123.txt
```

### 3. Terminal Emulator Fallback
Falls back to launching a new terminal window:
```bash
# Tries xterm, alacritty, kitty in order
xterm -e vim /tmp/mcp_edit_abc123.txt
```

## Usage Examples

### Email Composition
```json
{
  "tool": "prompt_user_edit",
  "arguments": {
    "content": "Subject: Project Update\n\nHi team,\n\nI wanted to provide an update...",
    "file_extension": ".md",
    "instructions": "Please refine this email for professional tone and clarity"
  }
}
```

### Commit Message Editing
```json
{
  "tool": "prompt_user_edit", 
  "arguments": {
    "content": "feat: add user authentication\n\n- Implement JWT token handling\n- Add login/logout endpoints",
    "file_extension": ".txt",
    "instructions": "Review and refine this commit message following conventional commits"
  }
}
```

### Code Review
```json
{
  "tool": "prompt_user_edit",
  "arguments": {
    "content": "def calculate_total(items):\n    return sum(item.price for item in items)",
    "file_extension": ".py", 
    "instructions": "Add error handling and documentation"
  }
}
```

## Response Format

The server returns detailed information about user changes:

```
📝 **Changes Summary:**
- **Lines added:** 3
- **Lines removed:** 1  
- **Net change:** +2 lines

**Diff:**
```diff
@@ -1,4 +1,6 @@
 Subject: Project Update
 
+Hi team,
+
 I wanted to provide an update on our current progress.
-Best regards
+Best regards,
+Will
```

**Updated Content:**
```
[Full edited content here...]
```
```

## File Type Support

The server recognizes common file extensions and provides appropriate:
- Syntax highlighting in vim
- Comment character detection for instructions
- Language-specific editing context

**Supported Extensions:**
- `.py` - Python (comments: `#`)
- `.js`, `.ts` - JavaScript/TypeScript (comments: `//`)
- `.md` - Markdown (comments: `<!--`)
- `.sql` - SQL (comments: `--`)
- `.vim` - Vim script (comments: `"`)
- `.txt` - Plain text (comments: `#`)

## Security Features

- **Temporary Files**: All editing happens in secure temporary files
- **Automatic Cleanup**: Files are removed after editing (unless `keep_file=true`)
- **Path Isolation**: No access to user's file system beyond temp directory
- **Content Validation**: Input sanitization for file operations

## Error Handling

The server gracefully handles various error conditions:

- **Vim Not Available**: Provides clear error message with installation guidance
- **No Terminal Access**: Falls back through multiple terminal options
- **User Cancellation**: Detects when user exits without saving
- **File Permission Issues**: Handles temporary file creation failures
- **tmux Session Problems**: Falls back to direct vim or terminal emulator

## Development & Testing

### Running Tests
```bash
# Unit tests
python -m pytest tests/unit/test_vim_server.py -v

# Integration tests  
python -m pytest tests/integration/test_server_integration.py::TestVimIntegration -v

# Coverage report
python -m pytest tests/unit/test_vim_server.py --cov=mcp_handley_lab.vim --cov-report=term-missing
```

### Manual Testing
```bash
# Test server directly
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | python -m mcp_handley_lab.vim.server

# Test tool call
echo '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"prompt_user_edit","arguments":{"content":"Hello world"}},"id":1}' | python -m mcp_handley_lab.vim.server
```

## Troubleshooting

### Common Issues

**"vim not found"**
```bash
# Install vim
sudo apt install vim        # Ubuntu/Debian
sudo yum install vim        # CentOS/RHEL  
brew install vim            # macOS
```

**"redirected stdin is pseudofile"**
- This occurs when running without proper terminal access
- Ensure you're in a real terminal session or tmux
- The server will automatically try fallback methods

**"No suitable terminal found"**
```bash
# Install a supported terminal emulator
sudo apt install xterm alacritty
```

**tmux window issues**
- Ensure tmux session is properly configured
- Check tmux version compatibility (2.0+)
- Verify tmux socket permissions

### Debug Mode

Set environment variable for detailed logging:
```bash
export VIM_MCP_DEBUG=1
python -m mcp_handley_lab.vim.server
```

## Integration with Claude Code

The vim MCP server is designed to work seamlessly with Claude Code workflows:

1. **Claude generates initial content** (emails, commit messages, documentation)
2. **User refines content** using familiar vim editor
3. **Claude receives precise changes** to understand user preferences
4. **Claude applies similar patterns** to future content generation

This creates a collaborative editing workflow where Claude provides the foundation and users add the finishing touches using their preferred editor.

## License

MIT License - see main package documentation for details.

## Contributing

Contributions welcome! Please see the main repository for development guidelines and testing requirements.
```

`mcp_handley_lab/vim/requirements.txt`:

```txt
# No external dependencies required
# The vim MCP server only uses Python standard library modules:
# - os, sys, tempfile, subprocess, difflib
# - typing (built-in since Python 3.5)
```

`mcp_handley_lab/vim/schemas.yml`:

```yml
tools:
  server_info:
    name: server_info
    description: Get Vim server status and error information
    inputSchema:
      type: object
      properties: {}
      required: []
    annotations:
      title: Vim Server Info
      readOnlyHint: true
      destructiveHint: false
      idempotentHint: true
      openWorldHint: false

  prompt_user_edit:
    name: prompt_user_edit
    description: Create a temporary file with content, open vim for user editing, and return the changes made
    inputSchema:
      type: object
      properties:
        content:
          type: string
          description: Initial content to edit
        file_extension:
          type: string
          description: File extension for syntax highlighting (.md, .txt, .py, etc.)
          default: ".txt"
        instructions:
          type: string
          description: Instructions to show user (as comments at top of file)
        show_diff:
          type: boolean
          description: If true, return diff of changes. If false, return full edited content.
          default: true
        keep_file:
          type: boolean
          description: If true, keep the temporary file and return its path
          default: false
      required: [content]
    annotations:
      title: Prompt User Edit
      readOnlyHint: false
      destructiveHint: false
      idempotentHint: false
      openWorldHint: false

  quick_edit:
    name: quick_edit
    description: Open vim to create new content from scratch
    inputSchema:
      type: object
      properties:
        file_extension:
          type: string
          description: File extension for syntax highlighting (.md, .txt, .py, etc.)
          default: ".txt"
        instructions:
          type: string
          description: Instructions to show user (as comments at top of file)
        initial_content:
          type: string
          description: Optional initial content to start with
          default: ""
      required: []
    annotations:
      title: Quick Edit
      readOnlyHint: false
      destructiveHint: false
      idempotentHint: false
      openWorldHint: false
```

`mcp_handley_lab/vim/server.py`:

```py
#!/usr/bin/env python3
"""
FastMCP-based Vim Server
Modern implementation using the official python-sdk
"""

import os
import sys
import tempfile
import subprocess
import difflib
import shutil
from typing import Dict, Any, List, Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic_settings import BaseSettings


class VimSettings(BaseSettings):
    """Settings for Vim server"""
    editor_command: str = "vim"
    
    class Config:
        env_prefix = "VIM_"


# Initialize settings and vim availability at module level
settings = VimSettings()

# Check if vim is available
vim_available = False
error_message = ""
editor_command = settings.editor_command

if shutil.which(settings.editor_command):
    vim_available = True
    editor_command = settings.editor_command
    error_message = ""
else:
    vim_available = False
    error_message = f"vim editor not found. Please install vim or set VIM_EDITOR_COMMAND environment variable"


# Create FastMCP app
mcp = FastMCP(
    "Vim MCP Server",
    instructions="Provides interactive editing with vim and change tracking. Opens vim for user editing and returns changes made."
)




def create_diff(original: str, modified: str, filename: str = "content") -> str:
    """Create a unified diff between original and modified content"""
    original_lines = original.splitlines(keepends=True)
    modified_lines = modified.splitlines(keepends=True)
    
    diff = list(difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
        n=3
    ))
    
    return ''.join(diff)


@mcp.tool(
    name="prompt_user_edit",
    description="Opens vim with the provided content for the user to edit interactively. Returns a summary of the changes made.",
    annotations=ToolAnnotations(
        title="Prompt User Edit with Vim",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False
    )
)
def prompt_user_edit(
    content: str,
    file_extension: str = ".txt",
    instructions: Optional[str] = None,
    show_diff: bool = True,
    keep_file: bool = False
) -> str:
    """Open vim to edit content and return changes"""
    
    if not vim_available:
        raise RuntimeError(f"vim is not available: {error_message}")
    
    try:
        # Create temporary file with initial content
        with tempfile.NamedTemporaryFile(
            mode='w+',
            suffix=file_extension,
            delete=False,
            encoding='utf-8'
        ) as temp_file:
            
            
            # Write the initial content
            temp_file.write(content)
            temp_file.flush()
            temp_path = temp_file.name
        
        # Store original content for diff comparison
        original_content = content
        
        # Open vim for editing - try different approaches for TTY access
        try:
            # Check if we have a TTY
            if os.isatty(sys.stdin.fileno()):
                # We have a TTY, use direct subprocess
                result = subprocess.run([editor_command, temp_path])
                if result.returncode != 0:
                    raise RuntimeError(f"Vim exited with error code {result.returncode}. File may not have been saved.")
            elif os.environ.get('TMUX'):
                # We're in a tmux session - use tmux integration
                try:
                    # Test if we can actually access tmux session
                    test_result = subprocess.run(['tmux', 'list-sessions'], 
                                               capture_output=True, text=True)
                    if test_result.returncode != 0:
                        raise subprocess.CalledProcessError(test_result.returncode, 'tmux')
                        
                    # Get current window info
                    current_info = subprocess.run([
                        'tmux', 'display-message', '-p', '#{window_id}:#{window_name}:#{window_index}'
                    ], capture_output=True, text=True, check=True).stdout.strip()
                    
                    current_window_id, current_window_name, current_window_index = current_info.split(':')
                    
                    # Create descriptive name for vim window
                    vim_window_name = f"vim→{current_window_name}"
                    
                    # Create new tmux window right after current one for editing
                    vim_window_result = subprocess.run([
                        'tmux', 'new-window', '-a', '-t', current_window_index,
                        '-n', vim_window_name, '-P', '-F', '#{window_id}',
                        f'vim "{temp_path}"; tmux select-window -t "{current_window_id}"'
                    ], capture_output=True, text=True, check=True)
                    
                    vim_window_id = vim_window_result.stdout.strip()
                    
                    # Wait for vim to finish with timeout
                    import time
                    max_wait_time = 300  # 5 minutes maximum
                    start_time = time.time()
                    
                    while time.time() - start_time < max_wait_time:
                        check_result = subprocess.run([
                            'tmux', 'list-windows', '-f', f'#{{==:#{{window_id}},{vim_window_id}}}'
                        ], capture_output=True, text=True)
                        if not check_result.stdout.strip():
                            break  # Vim window no longer exists (user closed vim)
                        time.sleep(0.1)
                    else:
                        # Timeout reached - force cleanup
                        subprocess.run(['tmux', 'kill-window', '-t', vim_window_id], 
                                     capture_output=True, check=False)
                        
                    # Cleanup
                    try:
                        subprocess.run(['tmux', 'kill-window', '-t', vim_window_id], 
                                     capture_output=True, check=False)
                    except:
                        pass  # Window might already be gone
                        
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired, Exception):
                    # tmux integration failed - fall back to manual editing
                    raise RuntimeError("No interactive terminal (TTY) is available to open vim.")
            else:
                # No TTY and no tmux - return manual editing instructions
                raise RuntimeError("No interactive terminal (TTY) is available to open vim.")
                
        except Exception as e:
            raise RuntimeError(f"Error opening vim: {e}")
        
        # Read the modified content
        try:
            with open(temp_path, 'r', encoding='utf-8') as f:
                modified_content = f.read()
        except Exception as e:
            raise IOError(f"Error reading file after edit: {e}")
        
        
        # Prepare response
        if show_diff:
            # Create and return diff
            diff = create_diff(original_content, modified_content)
            
            if not diff.strip():
                result_text = "✅ **No Changes Made**\n\nThe content was not modified during editing."
            else:
                result_text = f"✅ **Changes Made**\n\n```diff\n{diff}\n```"
        else:
            # Return full modified content
            result_text = f"✅ **Edited Content**\n\n```{file_extension}\n{modified_content}\n```"
        
        # Add file info if keeping the file
        if keep_file:
            result_text += f"\n\n📁 **Temporary File:** `{temp_path}`\n🔧 **Action:** File preserved for further use"
        else:
            # Clean up temporary file
            try:
                os.unlink(temp_path)
            except:
                pass  # Ignore cleanup errors
        
        return result_text
        
    except Exception as e:
        raise RuntimeError(f"Error during vim editing: {e}")


@mcp.tool(
    name="quick_edit",
    description="Opens vim with a blank (or pre-filled) buffer for the user to create new content from scratch. Returns the final content.",
    annotations=ToolAnnotations(
        title="Quick Edit with Vim",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False
    )
)
def quick_edit(
    file_extension: str = ".txt",
    instructions: Optional[str] = None,
    initial_content: str = ""
) -> str:
    """Open vim to create new content from scratch"""
    
    if not vim_available:
        raise RuntimeError(f"vim is not available: {error_message}")
    
    try:
        # Create temporary file for editing
        with tempfile.NamedTemporaryFile(
            mode='w+',
            suffix=file_extension,
            delete=False,
            encoding='utf-8'
        ) as temp_file:
            
            
            # Write initial content if provided
            if initial_content:
                temp_file.write(initial_content)
            
            temp_file.flush()
            temp_path = temp_file.name
        
        # Open vim for editing
        try:
            result = subprocess.run(
                [editor_command, temp_path],
                stdin=None,
                stdout=None,
                stderr=None,
                check=False
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"Vim exited with error code {result.returncode}. Content may not have been saved.")
            
        except Exception as e:
            raise RuntimeError(f"Error opening vim: {e}")
        
        # Read the created content
        try:
            with open(temp_path, 'r', encoding='utf-8') as f:
                created_content = f.read()
        except Exception as e:
            raise IOError(f"Error reading created file: {e}")
        
        
        # Clean up temporary file
        try:
            os.unlink(temp_path)
        except:
            pass  # Ignore cleanup errors
        
        # Return the created content
        if created_content.strip():
            return f"✅ **Content Created**\n\n```{file_extension}\n{created_content}\n```"
        else:
            return "✅ **Empty Content**\n\nNo content was created (file is empty)."
        
    except Exception as e:
        raise RuntimeError(f"Error during vim editing: {e}")


@mcp.tool(
    name="open_file",
    description="Opens an existing local file in vim for the user to edit. Requires a direct file_path. Returns a summary of the changes.",
    annotations=ToolAnnotations(
        title="Open File in Vim",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False
    )
)
def open_file(
    file_path: str,
    instructions: Optional[str] = None,
    show_diff: bool = True,
    backup: bool = True
) -> str:
    """Open an existing file in vim for editing"""
    
    if not vim_available:
        raise RuntimeError(f"vim is not available: {error_message}")
    
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Read original content for diff comparison
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
        except Exception as e:
            raise IOError(f"Error reading file '{file_path}': {e}")
        
        # Create backup if requested
        backup_path = None
        if backup:
            try:
                backup_path = f"{file_path}.backup"
                shutil.copy2(file_path, backup_path)
            except Exception as e:
                raise IOError(f"Error creating backup for '{file_path}': {e}")
        
        edit_path = file_path
        
        # Open vim for editing
        try:
            # Check if we have a TTY
            if os.isatty(sys.stdin.fileno()):
                result = subprocess.run([editor_command, edit_path])
                if result.returncode != 0:
                    raise RuntimeError(f"Vim exited with error code {result.returncode}. File may not have been saved.")
            elif os.environ.get('TMUX'):
                # Use tmux integration
                try:
                    test_result = subprocess.run(['tmux', 'list-sessions'], 
                                               capture_output=True, text=True)
                    if test_result.returncode != 0:
                        raise subprocess.CalledProcessError(test_result.returncode, 'tmux')
                    
                    current_info = subprocess.run([
                        'tmux', 'display-message', '-p', '#{window_id}:#{window_name}:#{window_index}'
                    ], capture_output=True, text=True, check=True).stdout.strip()
                    
                    current_window_id, current_window_name, current_window_index = current_info.split(':')
                    vim_window_name = f"vim→{os.path.basename(file_path)}"
                    
                    vim_window_result = subprocess.run([
                        'tmux', 'new-window', '-a', '-t', current_window_index,
                        '-n', vim_window_name, '-P', '-F', '#{window_id}',
                        f'vim "{edit_path}"; tmux select-window -t "{current_window_id}"'
                    ], capture_output=True, text=True, check=True)
                    
                    vim_window_id = vim_window_result.stdout.strip()
                    
                    import time
                    max_wait_time = 300
                    start_time = time.time()
                    
                    while time.time() - start_time < max_wait_time:
                        check_result = subprocess.run([
                            'tmux', 'list-windows', '-f', f'#{{==:#{{window_id}},{vim_window_id}}}'
                        ], capture_output=True, text=True)
                        if not check_result.stdout.strip():
                            break
                        time.sleep(0.1)
                    else:
                        subprocess.run(['tmux', 'kill-window', '-t', vim_window_id], 
                                     capture_output=True, check=False)
                    
                    try:
                        subprocess.run(['tmux', 'kill-window', '-t', vim_window_id], 
                                     capture_output=True, check=False)
                    except:
                        pass
                        
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired, Exception):
                    raise RuntimeError("No interactive terminal (TTY) is available to open vim.")
            else:
                raise RuntimeError("No interactive terminal (TTY) is available to open vim.")
                
        except Exception as e:
            raise RuntimeError(f"Error opening vim: {e}")
        
        # Read modified content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                modified_content = f.read()
        except Exception as e:
            raise IOError(f"Error reading file after edit: {e}")
        
        # Prepare response
        if show_diff:
            diff = create_diff(original_content, modified_content, os.path.basename(file_path))
            
            if not diff.strip():
                result_text = "✅ **No Changes Made**\n\nThe file was not modified during editing."
            else:
                result_text = f"✅ **File Modified**\n\n```diff\n{diff}\n```"
        else:
            result_text = f"✅ **File Edited**\n\nFile `{file_path}` has been modified."
        
        # Add backup info
        if backup and backup_path:
            result_text += f"\n\n💾 **Backup Created:** `{backup_path}`"
        
        return result_text
        
    except Exception as e:
        raise RuntimeError(f"Error editing file: {e}")


@mcp.tool(
    name="server_info",
    description="Checks the vim server status and verifies that the vim editor is installed and available.",
    annotations=ToolAnnotations(
        title="Vim Server Status",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False
    )
)
def server_info() -> str:
    """Get server status and configuration info"""
    if vim_available:
        # Get vim version info
        try:
            result = subprocess.run(
                [editor_command, '--version'],
                capture_output=True,
                text=True
            )
            version_line = result.stdout.split('\n')[0] if result.stdout else "Unknown version"
        except:
            version_line = "Unknown version"
        
        return f"""✅ **Vim Server Available**

🔧 **Configuration:**
- Editor Command: {editor_command}
- Version: {version_line}

🛠️ **Available Tools:**
- prompt_user_edit: Edit existing content with vim and see changes
- quick_edit: Create new content from scratch with vim
- open_file: Open and edit existing files directly
- server_info: This status information

💡 **Usage Tips:**
- Use instructions parameter to guide the editing process
- show_diff=true shows changes made, show_diff=false shows full content
- keep_file=true preserves temporary files for further use
- File extensions enable syntax highlighting (.py, .js, .md, etc.)
- Vim opens in the terminal - use normal vim commands to edit

⚠️ **Important:** This requires a terminal environment where vim can be opened interactively."""
    else:
        return f"""❌ **Vim Server Unavailable**

🔴 **Error:** {error_message}

🔧 **Setup Required:**
1. Install vim: 
   - Ubuntu/Debian: `sudo apt-get install vim`
   - macOS: `brew install vim` (or use built-in vim)
   - Windows: Install vim from https://www.vim.org/download.php
2. Ensure vim is in your PATH
3. Restart the server

💡 **Alternative:** Set VIM_EDITOR_COMMAND environment variable to use a different editor"""


def main():
    """Main entry point"""
    # Run with stdio transport (synchronous)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
```

`mcp_handley_lab/vim/test_server.py`:

```py
#!/usr/bin/env python3
"""
Test suite for Vim MCP server
"""

import json
import subprocess
import tempfile
import os
import sys
from typing import Dict, Any

# Add the parent directory to path to import server
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def call_server(method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """Call the vim server with a JSON-RPC request"""
    request = {"jsonrpc": "2.0", "method": method, "id": 1}
    if params:
        request["params"] = params
    
    server_path = os.path.join(os.path.dirname(__file__), 'server.py')
    process = subprocess.Popen(
        ['python', server_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    stdout, stderr = process.communicate(json.dumps(request))
    if process.returncode != 0:
        raise Exception(f"Server error: {stderr}")
    
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse server response: {stdout}\nError: {e}")

def test_server_initialization():
    """Test that server initializes correctly"""
    response = call_server("initialize")
    assert "result" in response
    assert response["result"]["serverInfo"]["name"] == "vim-mcp"
    print("✅ Server initialization test passed")

def test_tools_list():
    """Test that all tools are properly registered"""
    response = call_server("tools/list")
    assert "result" in response
    assert "tools" in response["result"]
    
    # Verify expected tools are present
    tool_names = [tool["name"] for tool in response["result"]["tools"]]
    expected_tools = ["server_info", "prompt_user_edit", "quick_edit"]
    for tool in expected_tools:
        assert tool in tool_names, f"Tool '{tool}' not found in {tool_names}"
    
    print("✅ Tools list test passed")

def test_server_info():
    """Test server info tool"""
    response = call_server("tools/call", {
        "name": "server_info",
        "arguments": {}
    })
    
    assert "result" in response
    assert "content" in response["result"]
    content = response["result"]["content"][0]["text"]
    
    # Should contain server version info
    assert "vim-mcp" in content.lower() or "vim" in content.lower()
    print("✅ Server info test passed")

def test_change_detection():
    """Test the diff generation functionality directly"""
    from vim.server import VimServer
    
    server = VimServer()
    
    original = "Hello world\nThis is a test\nEnd of file"
    edited = "Hello universe\nThis is a test\nAdded new line\nEnd of file"
    
    changes = server._get_changes_summary(original, edited)
    
    # Should detect changes
    assert "Changes Summary" in changes
    assert "Lines added:" in changes
    assert "Lines removed:" in changes
    assert "Diff:" in changes
    
    print("✅ Change detection test passed")

def test_no_changes():
    """Test behavior when no changes are made"""
    from vim.server import VimServer
    
    server = VimServer()
    
    content = "Hello world\nThis is a test"
    changes = server._get_changes_summary(content, content)
    
    # Should detect no changes
    assert "No Changes Made" in changes
    
    print("✅ No changes test passed")

def test_comment_char_detection():
    """Test comment character detection for different file types"""
    from vim.server import VimServer
    
    server = VimServer()
    
    test_cases = {
        '.py': '#',
        '.js': '//',
        '.sql': '--',
        '.md': '<!--',
        '.unknown': '#'  # Default fallback
    }
    
    for ext, expected in test_cases.items():
        actual = server._get_comment_char(ext)
        assert actual == expected, f"Expected {expected} for {ext}, got {actual}"
    
    print("✅ Comment character detection test passed")

def test_tool_schema_structure():
    """Test that tool schemas have required MCP annotations"""
    from vim.server import VimServer
    
    server = VimServer()
    tools = server.get_tools()
    
    for tool in tools:
        # Check required MCP tool structure
        assert "name" in tool
        assert "description" in tool
        assert "inputSchema" in tool
        assert "annotations" in tool
        
        # Check required annotations
        annotations = tool["annotations"]
        required_annotations = ["title", "readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint"]
        for annotation in required_annotations:
            assert annotation in annotations, f"Missing annotation '{annotation}' in tool '{tool['name']}'"
    
    print("✅ Tool schema structure test passed")

def run_all_tests():
    """Run all tests"""
    print("🧪 Running Vim MCP Server Tests...\n")
    
    try:
        test_server_initialization()
        test_tools_list()
        test_server_info()
        test_change_detection()
        test_no_changes()
        test_comment_char_detection()
        test_tool_schema_structure()
        
        print("\n🎉 All tests passed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
```

=========== PYTHON SDK README ===========

# MCP Python SDK

<div align="center">

<strong>Python implementation of the Model Context Protocol (MCP)</strong>

[![PyPI][pypi-badge]][pypi-url]
[![MIT licensed][mit-badge]][mit-url]
[![Python Version][python-badge]][python-url]
[![Documentation][docs-badge]][docs-url]
[![Specification][spec-badge]][spec-url]
[![GitHub Discussions][discussions-badge]][discussions-url]

</div>

<!-- omit in toc -->
## Table of Contents

- [MCP Python SDK](#mcp-python-sdk)
  - [Overview](#overview)
  - [Installation](#installation)
    - [Adding MCP to your python project](#adding-mcp-to-your-python-project)
    - [Running the standalone MCP development tools](#running-the-standalone-mcp-development-tools)
  - [Quickstart](#quickstart)
  - [What is MCP?](#what-is-mcp)
  - [Core Concepts](#core-concepts)
    - [Server](#server)
    - [Resources](#resources)
    - [Tools](#tools)
    - [Prompts](#prompts)
    - [Images](#images)
    - [Context](#context)
    - [Completions](#completions)
    - [Elicitation](#elicitation)
    - [Authentication](#authentication)
  - [Running Your Server](#running-your-server)
    - [Development Mode](#development-mode)
    - [Claude Desktop Integration](#claude-desktop-integration)
    - [Direct Execution](#direct-execution)
    - [Mounting to an Existing ASGI Server](#mounting-to-an-existing-asgi-server)
  - [Examples](#examples)
    - [Echo Server](#echo-server)
    - [SQLite Explorer](#sqlite-explorer)
  - [Advanced Usage](#advanced-usage)
    - [Low-Level Server](#low-level-server)
    - [Writing MCP Clients](#writing-mcp-clients)
    - [MCP Primitives](#mcp-primitives)
    - [Server Capabilities](#server-capabilities)
  - [Documentation](#documentation)
  - [Contributing](#contributing)
  - [License](#license)

[pypi-badge]: https://img.shields.io/pypi/v/mcp.svg
[pypi-url]: https://pypi.org/project/mcp/
[mit-badge]: https://img.shields.io/pypi/l/mcp.svg
[mit-url]: https://github.com/modelcontextprotocol/python-sdk/blob/main/LICENSE
[python-badge]: https://img.shields.io/pypi/pyversions/mcp.svg
[python-url]: https://www.python.org/downloads/
[docs-badge]: https://img.shields.io/badge/docs-modelcontextprotocol.io-blue.svg
[docs-url]: https://modelcontextprotocol.io
[spec-badge]: https://img.shields.io/badge/spec-spec.modelcontextprotocol.io-blue.svg
[spec-url]: https://spec.modelcontextprotocol.io
[discussions-badge]: https://img.shields.io/github/discussions/modelcontextprotocol/python-sdk
[discussions-url]: https://github.com/modelcontextprotocol/python-sdk/discussions

## Overview

The Model Context Protocol allows applications to provide context for LLMs in a standardized way, separating the concerns of providing context from the actual LLM interaction. This Python SDK implements the full MCP specification, making it easy to:

- Build MCP clients that can connect to any MCP server
- Create MCP servers that expose resources, prompts and tools
- Use standard transports like stdio, SSE, and Streamable HTTP
- Handle all MCP protocol messages and lifecycle events

## Installation

### Adding MCP to your python project

We recommend using [uv](https://docs.astral.sh/uv/) to manage your Python projects.

If you haven't created a uv-managed project yet, create one:

   ```bash
   uv init mcp-server-demo
   cd mcp-server-demo
   ```

   Then add MCP to your project dependencies:

   ```bash
   uv add "mcp[cli]"
   ```

Alternatively, for projects using pip for dependencies:
```bash
pip install "mcp[cli]"
```

### Running the standalone MCP development tools

To run the mcp command with uv:

```bash
uv run mcp
```

## Quickstart

Let's create a simple MCP server that exposes a calculator tool and some data:

```python
# server.py
from mcp.server.fastmcp import FastMCP

# Create an MCP server
mcp = FastMCP("Demo")


# Add an addition tool
@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b


# Add a dynamic greeting resource
@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """Get a personalized greeting"""
    return f"Hello, {name}!"
```

You can install this server in [Claude Desktop](https://claude.ai/download) and interact with it right away by running:
```bash
mcp install server.py
```

Alternatively, you can test it with the MCP Inspector:
```bash
mcp dev server.py
```

## What is MCP?

The [Model Context Protocol (MCP)](https://modelcontextprotocol.io) lets you build servers that expose data and functionality to LLM applications in a secure, standardized way. Think of it like a web API, but specifically designed for LLM interactions. MCP servers can:

- Expose data through **Resources** (think of these sort of like GET endpoints; they are used to load information into the LLM's context)
- Provide functionality through **Tools** (sort of like POST endpoints; they are used to execute code or otherwise produce a side effect)
- Define interaction patterns through **Prompts** (reusable templates for LLM interactions)
- And more!

## Core Concepts

### Server

The FastMCP server is your core interface to the MCP protocol. It handles connection management, protocol compliance, and message routing:

```python
# Add lifespan support for startup/shutdown with strong typing
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass

from fake_database import Database  # Replace with your actual DB type

from mcp.server.fastmcp import FastMCP

# Create a named server
mcp = FastMCP("My App")

# Specify dependencies for deployment and development
mcp = FastMCP("My App", dependencies=["pandas", "numpy"])


@dataclass
class AppContext:
    db: Database


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage application lifecycle with type-safe context"""
    # Initialize on startup
    db = await Database.connect()
    try:
        yield AppContext(db=db)
    finally:
        # Cleanup on shutdown
        await db.disconnect()


# Pass lifespan to server
mcp = FastMCP("My App", lifespan=app_lifespan)


# Access type-safe lifespan context in tools
@mcp.tool()
def query_db() -> str:
    """Tool that uses initialized resources"""
    ctx = mcp.get_context()
    db = ctx.request_context.lifespan_context["db"]
    return db.query()
```

### Resources

Resources are how you expose data to LLMs. They're similar to GET endpoints in a REST API - they provide data but shouldn't perform significant computation or have side effects:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("My App")


@mcp.resource("config://app", title="Application Configuration")
def get_config() -> str:
    """Static configuration data"""
    return "App configuration here"


@mcp.resource("users://{user_id}/profile", title="User Profile")
def get_user_profile(user_id: str) -> str:
    """Dynamic user data"""
    return f"Profile data for user {user_id}"
```

### Tools

Tools let LLMs take actions through your server. Unlike resources, tools are expected to perform computation and have side effects:

```python
import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("My App")


@mcp.tool(title="BMI Calculator")
def calculate_bmi(weight_kg: float, height_m: float) -> float:
    """Calculate BMI given weight in kg and height in meters"""
    return weight_kg / (height_m**2)


@mcp.tool(title="Weather Fetcher")
async def fetch_weather(city: str) -> str:
    """Fetch current weather for a city"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.weather.com/{city}")
        return response.text
```

### Prompts

Prompts are reusable templates that help LLMs interact with your server effectively:

```python
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts import base

mcp = FastMCP("My App")


@mcp.prompt(title="Code Review")
def review_code(code: str) -> str:
    return f"Please review this code:\n\n{code}"


@mcp.prompt(title="Debug Assistant")
def debug_error(error: str) -> list[base.Message]:
    return [
        base.UserMessage("I'm seeing this error:"),
        base.UserMessage(error),
        base.AssistantMessage("I'll help debug that. What have you tried so far?"),
    ]
```

### Images

FastMCP provides an `Image` class that automatically handles image data:

```python
from mcp.server.fastmcp import FastMCP, Image
from PIL import Image as PILImage

mcp = FastMCP("My App")


@mcp.tool()
def create_thumbnail(image_path: str) -> Image:
    """Create a thumbnail from an image"""
    img = PILImage.open(image_path)
    img.thumbnail((100, 100))
    return Image(data=img.tobytes(), format="png")
```

### Context

The Context object gives your tools and resources access to MCP capabilities:

```python
from mcp.server.fastmcp import FastMCP, Context

mcp = FastMCP("My App")


@mcp.tool()
async def long_task(files: list[str], ctx: Context) -> str:
    """Process multiple files with progress tracking"""
    for i, file in enumerate(files):
        ctx.info(f"Processing {file}")
        await ctx.report_progress(i, len(files))
        data, mime_type = await ctx.read_resource(f"file://{file}")
    return "Processing complete"
```

### Completions

MCP supports providing completion suggestions for prompt arguments and resource template parameters. With the context parameter, servers can provide completions based on previously resolved values:

Client usage:
```python
from mcp.client.session import ClientSession
from mcp.types import ResourceTemplateReference


async def use_completion(session: ClientSession):
    # Complete without context
    result = await session.complete(
        ref=ResourceTemplateReference(
            type="ref/resource", uri="github://repos/{owner}/{repo}"
        ),
        argument={"name": "owner", "value": "model"},
    )

    # Complete with context - repo suggestions based on owner
    result = await session.complete(
        ref=ResourceTemplateReference(
            type="ref/resource", uri="github://repos/{owner}/{repo}"
        ),
        argument={"name": "repo", "value": "test"},
        context_arguments={"owner": "modelcontextprotocol"},
    )
```

Server implementation:
```python
from mcp.server import Server
from mcp.types import (
    Completion,
    CompletionArgument,
    CompletionContext,
    PromptReference,
    ResourceTemplateReference,
)

server = Server("example-server")


@server.completion()
async def handle_completion(
    ref: PromptReference | ResourceTemplateReference,
    argument: CompletionArgument,
    context: CompletionContext | None,
) -> Completion | None:
    if isinstance(ref, ResourceTemplateReference):
        if ref.uri == "github://repos/{owner}/{repo}" and argument.name == "repo":
            # Use context to provide owner-specific repos
            if context and context.arguments:
                owner = context.arguments.get("owner")
                if owner == "modelcontextprotocol":
                    repos = ["python-sdk", "typescript-sdk", "specification"]
                    # Filter based on partial input
                    filtered = [r for r in repos if r.startswith(argument.value)]
                    return Completion(values=filtered)
    return None
```
### Elicitation

Request additional information from users during tool execution:

```python
from mcp.server.fastmcp import FastMCP, Context
from mcp.server.elicitation import (
    AcceptedElicitation,
    DeclinedElicitation,
    CancelledElicitation,
)
from pydantic import BaseModel, Field

mcp = FastMCP("Booking System")


@mcp.tool()
async def book_table(date: str, party_size: int, ctx: Context) -> str:
    """Book a table with confirmation"""

    # Schema must only contain primitive types (str, int, float, bool)
    class ConfirmBooking(BaseModel):
        confirm: bool = Field(description="Confirm booking?")
        notes: str = Field(default="", description="Special requests")

    result = await ctx.elicit(
        message=f"Confirm booking for {party_size} on {date}?", schema=ConfirmBooking
    )

    match result:
        case AcceptedElicitation(data=data):
            if data.confirm:
                return f"Booked! Notes: {data.notes or 'None'}"
            return "Booking cancelled"
        case DeclinedElicitation():
            return "Booking declined"
        case CancelledElicitation():
            return "Booking cancelled"
```

The `elicit()` method returns an `ElicitationResult` with:
- `action`: "accept", "decline", or "cancel"
- `data`: The validated response (only when accepted)
- `validation_error`: Any validation error message

### Authentication

Authentication can be used by servers that want to expose tools accessing protected resources.

`mcp.server.auth` implements an OAuth 2.0 server interface, which servers can use by
providing an implementation of the `OAuthAuthorizationServerProvider` protocol.

```python
from mcp import FastMCP
from mcp.server.auth.provider import OAuthAuthorizationServerProvider
from mcp.server.auth.settings import (
    AuthSettings,
    ClientRegistrationOptions,
    RevocationOptions,
)


class MyOAuthServerProvider(OAuthAuthorizationServerProvider):
    # See an example on how to implement at `examples/servers/simple-auth`
    ...


mcp = FastMCP(
    "My App",
    auth_server_provider=MyOAuthServerProvider(),
    auth=AuthSettings(
        issuer_url="https://myapp.com",
        revocation_options=RevocationOptions(
            enabled=True,
        ),
        client_registration_options=ClientRegistrationOptions(
            enabled=True,
            valid_scopes=["myscope", "myotherscope"],
            default_scopes=["myscope"],
        ),
        required_scopes=["myscope"],
    ),
)
```

See [OAuthAuthorizationServerProvider](src/mcp/server/auth/provider.py) for more details.

## Running Your Server

### Development Mode

The fastest way to test and debug your server is with the MCP Inspector:

```bash
mcp dev server.py

# Add dependencies
mcp dev server.py --with pandas --with numpy

# Mount local code
mcp dev server.py --with-editable .
```

### Claude Desktop Integration

Once your server is ready, install it in Claude Desktop:

```bash
mcp install server.py

# Custom name
mcp install server.py --name "My Analytics Server"

# Environment variables
mcp install server.py -v API_KEY=abc123 -v DB_URL=postgres://...
mcp install server.py -f .env
```

### Direct Execution

For advanced scenarios like custom deployments:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("My App")

if __name__ == "__main__":
    mcp.run()
```

Run it with:
```bash
python server.py
# or
mcp run server.py
```

Note that `mcp run` or `mcp dev` only supports server using FastMCP and not the low-level server variant.

### Streamable HTTP Transport

> **Note**: Streamable HTTP transport is superseding SSE transport for production deployments.

```python
from mcp.server.fastmcp import FastMCP

# Stateful server (maintains session state)
mcp = FastMCP("StatefulServer")

# Stateless server (no session persistence)
mcp = FastMCP("StatelessServer", stateless_http=True)

# Stateless server (no session persistence, no sse stream with supported client)
mcp = FastMCP("StatelessServer", stateless_http=True, json_response=True)

# Run server with streamable_http transport
mcp.run(transport="streamable-http")
```

You can mount multiple FastMCP servers in a FastAPI application:

```python
# echo.py
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="EchoServer", stateless_http=True)


@mcp.tool(description="A simple echo tool")
def echo(message: str) -> str:
    return f"Echo: {message}"
```

```python
# math.py
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="MathServer", stateless_http=True)


@mcp.tool(description="A simple add tool")
def add_two(n: int) -> int:
    return n + 2
```

```python
# main.py
import contextlib
from fastapi import FastAPI
from mcp.echo import echo
from mcp.math import math


# Create a combined lifespan to manage both session managers
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    async with contextlib.AsyncExitStack() as stack:
        await stack.enter_async_context(echo.mcp.session_manager.run())
        await stack.enter_async_context(math.mcp.session_manager.run())
        yield


app = FastAPI(lifespan=lifespan)
app.mount("/echo", echo.mcp.streamable_http_app())
app.mount("/math", math.mcp.streamable_http_app())
```

For low level server with Streamable HTTP implementations, see:
- Stateful server: [`examples/servers/simple-streamablehttp/`](examples/servers/simple-streamablehttp/)
- Stateless server: [`examples/servers/simple-streamablehttp-stateless/`](examples/servers/simple-streamablehttp-stateless/)

The streamable HTTP transport supports:
- Stateful and stateless operation modes
- Resumability with event stores
- JSON or SSE response formats
- Better scalability for multi-node deployments

### Mounting to an Existing ASGI Server

> **Note**: SSE transport is being superseded by [Streamable HTTP transport](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports#streamable-http).

By default, SSE servers are mounted at `/sse` and Streamable HTTP servers are mounted at `/mcp`. You can customize these paths using the methods described below.

You can mount the SSE server to an existing ASGI server using the `sse_app` method. This allows you to integrate the SSE server with other ASGI applications.

```python
from starlette.applications import Starlette
from starlette.routing import Mount, Host
from mcp.server.fastmcp import FastMCP


mcp = FastMCP("My App")

# Mount the SSE server to the existing ASGI server
app = Starlette(
    routes=[
        Mount('/', app=mcp.sse_app()),
    ]
)

# or dynamically mount as host
app.router.routes.append(Host('mcp.acme.corp', app=mcp.sse_app()))
```

When mounting multiple MCP servers under different paths, you can configure the mount path in several ways:

```python
from starlette.applications import Starlette
from starlette.routing import Mount
from mcp.server.fastmcp import FastMCP

# Create multiple MCP servers
github_mcp = FastMCP("GitHub API")
browser_mcp = FastMCP("Browser")
curl_mcp = FastMCP("Curl")
search_mcp = FastMCP("Search")

# Method 1: Configure mount paths via settings (recommended for persistent configuration)
github_mcp.settings.mount_path = "/github"
browser_mcp.settings.mount_path = "/browser"

# Method 2: Pass mount path directly to sse_app (preferred for ad-hoc mounting)
# This approach doesn't modify the server's settings permanently

# Create Starlette app with multiple mounted servers
app = Starlette(
    routes=[
        # Using settings-based configuration
        Mount("/github", app=github_mcp.sse_app()),
        Mount("/browser", app=browser_mcp.sse_app()),
        # Using direct mount path parameter
        Mount("/curl", app=curl_mcp.sse_app("/curl")),
        Mount("/search", app=search_mcp.sse_app("/search")),
    ]
)

# Method 3: For direct execution, you can also pass the mount path to run()
if __name__ == "__main__":
    search_mcp.run(transport="sse", mount_path="/search")
```

For more information on mounting applications in Starlette, see the [Starlette documentation](https://www.starlette.io/routing/#submounting-routes).

## Examples

### Echo Server

A simple server demonstrating resources, tools, and prompts:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Echo")


@mcp.resource("echo://{message}")
def echo_resource(message: str) -> str:
    """Echo a message as a resource"""
    return f"Resource echo: {message}"


@mcp.tool()
def echo_tool(message: str) -> str:
    """Echo a message as a tool"""
    return f"Tool echo: {message}"


@mcp.prompt()
def echo_prompt(message: str) -> str:
    """Create an echo prompt"""
    return f"Please process this message: {message}"
```

### SQLite Explorer

A more complex example showing database integration:

```python
import sqlite3

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("SQLite Explorer")


@mcp.resource("schema://main")
def get_schema() -> str:
    """Provide the database schema as a resource"""
    conn = sqlite3.connect("database.db")
    schema = conn.execute("SELECT sql FROM sqlite_master WHERE type='table'").fetchall()
    return "\n".join(sql[0] for sql in schema if sql[0])


@mcp.tool()
def query_data(sql: str) -> str:
    """Execute SQL queries safely"""
    conn = sqlite3.connect("database.db")
    try:
        result = conn.execute(sql).fetchall()
        return "\n".join(str(row) for row in result)
    except Exception as e:
        return f"Error: {str(e)}"
```

## Advanced Usage

### Low-Level Server

For more control, you can use the low-level server implementation directly. This gives you full access to the protocol and allows you to customize every aspect of your server, including lifecycle management through the lifespan API:

```python
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fake_database import Database  # Replace with your actual DB type

from mcp.server import Server


@asynccontextmanager
async def server_lifespan(server: Server) -> AsyncIterator[dict]:
    """Manage server startup and shutdown lifecycle."""
    # Initialize resources on startup
    db = await Database.connect()
    try:
        yield {"db": db}
    finally:
        # Clean up on shutdown
        await db.disconnect()


# Pass lifespan to server
server = Server("example-server", lifespan=server_lifespan)


# Access lifespan context in handlers
@server.call_tool()
async def query_db(name: str, arguments: dict) -> list:
    ctx = server.request_context
    db = ctx.lifespan_context["db"]
    return await db.query(arguments["query"])
```

The lifespan API provides:
- A way to initialize resources when the server starts and clean them up when it stops
- Access to initialized resources through the request context in handlers
- Type-safe context passing between lifespan and request handlers

```python
import mcp.server.stdio
import mcp.types as types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions

# Create a server instance
server = Server("example-server")


@server.list_prompts()
async def handle_list_prompts() -> list[types.Prompt]:
    return [
        types.Prompt(
            name="example-prompt",
            description="An example prompt template",
            arguments=[
                types.PromptArgument(
                    name="arg1", description="Example argument", required=True
                )
            ],
        )
    ]


@server.get_prompt()
async def handle_get_prompt(
    name: str, arguments: dict[str, str] | None
) -> types.GetPromptResult:
    if name != "example-prompt":
        raise ValueError(f"Unknown prompt: {name}")

    return types.GetPromptResult(
        description="Example prompt",
        messages=[
            types.PromptMessage(
                role="user",
                content=types.TextContent(type="text", text="Example prompt text"),
            )
        ],
    )


async def run():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="example",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(run())
```

Caution: The `mcp run` and `mcp dev` tool doesn't support low-level server.

### Writing MCP Clients

The SDK provides a high-level client interface for connecting to MCP servers using various [transports](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports):

```python
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

# Create server parameters for stdio connection
server_params = StdioServerParameters(
    command="python",  # Executable
    args=["example_server.py"],  # Optional command line arguments
    env=None,  # Optional environment variables
)


# Optional: create a sampling callback
async def handle_sampling_message(
    message: types.CreateMessageRequestParams,
) -> types.CreateMessageResult:
    return types.CreateMessageResult(
        role="assistant",
        content=types.TextContent(
            type="text",
            text="Hello, world! from model",
        ),
        model="gpt-3.5-turbo",
        stopReason="endTurn",
    )


async def run():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(
            read, write, sampling_callback=handle_sampling_message
        ) as session:
            # Initialize the connection
            await session.initialize()

            # List available prompts
            prompts = await session.list_prompts()

            # Get a prompt
            prompt = await session.get_prompt(
                "example-prompt", arguments={"arg1": "value"}
            )

            # List available resources
            resources = await session.list_resources()

            # List available tools
            tools = await session.list_tools()

            # Read a resource
            content, mime_type = await session.read_resource("file://some/path")

            # Call a tool
            result = await session.call_tool("tool-name", arguments={"arg1": "value"})


if __name__ == "__main__":
    import asyncio

    asyncio.run(run())
```

Clients can also connect using [Streamable HTTP transport](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports#streamable-http):

```python
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession


async def main():
    # Connect to a streamable HTTP server
    async with streamablehttp_client("example/mcp") as (
        read_stream,
        write_stream,
        _,
    ):
        # Create a session using the client streams
        async with ClientSession(read_stream, write_stream) as session:
            # Initialize the connection
            await session.initialize()
            # Call a tool
            tool_result = await session.call_tool("echo", {"message": "hello"})
```

### Client Display Utilities

When building MCP clients, the SDK provides utilities to help display human-readable names for tools, resources, and prompts:

```python
from mcp.shared.metadata_utils import get_display_name
from mcp.client.session import ClientSession


async def display_tools(session: ClientSession):
    """Display available tools with human-readable names"""
    tools_response = await session.list_tools()

    for tool in tools_response.tools:
        # get_display_name() returns the title if available, otherwise the name
        display_name = get_display_name(tool)
        print(f"Tool: {display_name}")
        if tool.description:
            print(f"   {tool.description}")


async def display_resources(session: ClientSession):
    """Display available resources with human-readable names"""
    resources_response = await session.list_resources()

    for resource in resources_response.resources:
        display_name = get_display_name(resource)
        print(f"Resource: {display_name} ({resource.uri})")
```

The `get_display_name()` function implements the proper precedence rules for displaying names:
- For tools: `title` > `annotations.title` > `name`
- For other objects: `title` > `name`

This ensures your client UI shows the most user-friendly names that servers provide.

### OAuth Authentication for Clients

The SDK includes [authorization support](https://modelcontextprotocol.io/specification/2025-03-26/basic/authorization) for connecting to protected MCP servers:

```python
from mcp.client.auth import OAuthClientProvider, TokenStorage
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken


class CustomTokenStorage(TokenStorage):
    """Simple in-memory token storage implementation."""

    async def get_tokens(self) -> OAuthToken | None:
        pass

    async def set_tokens(self, tokens: OAuthToken) -> None:
        pass

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        pass

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        pass


async def main():
    # Set up OAuth authentication
    oauth_auth = OAuthClientProvider(
        server_url="https://api.example.com",
        client_metadata=OAuthClientMetadata(
            client_name="My Client",
            redirect_uris=["http://localhost:3000/callback"],
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
        ),
        storage=CustomTokenStorage(),
        redirect_handler=lambda url: print(f"Visit: {url}"),
        callback_handler=lambda: ("auth_code", None),
    )

    # Use with streamable HTTP client
    async with streamablehttp_client(
        "https://api.example.com/mcp", auth=oauth_auth
    ) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            # Authenticated session ready
```

For a complete working example, see [`examples/clients/simple-auth-client/`](examples/clients/simple-auth-client/).


### MCP Primitives

The MCP protocol defines three core primitives that servers can implement:

| Primitive | Control               | Description                                         | Example Use                  |
|-----------|-----------------------|-----------------------------------------------------|------------------------------|
| Prompts   | User-controlled       | Interactive templates invoked by user choice        | Slash commands, menu options |
| Resources | Application-controlled| Contextual data managed by the client application   | File contents, API responses |
| Tools     | Model-controlled      | Functions exposed to the LLM to take actions        | API calls, data updates      |

### Server Capabilities

MCP servers declare capabilities during initialization:

| Capability  | Feature Flag                 | Description                        |
|-------------|------------------------------|------------------------------------|
| `prompts`   | `listChanged`                | Prompt template management         |
| `resources` | `subscribe`<br/>`listChanged`| Resource exposure and updates      |
| `tools`     | `listChanged`                | Tool discovery and execution       |
| `logging`   | -                            | Server logging configuration       |
| `completion`| -                            | Argument completion suggestions    |

## Documentation

- [Model Context Protocol documentation](https://modelcontextprotocol.io)
- [Model Context Protocol specification](https://spec.modelcontextprotocol.io)
- [Officially supported servers](https://github.com/modelcontextprotocol/servers)

## Contributing

We are passionate about supporting contributors of all levels of experience and would love to see you get involved in the project. See the [contributing guide](CONTRIBUTING.md) to get started.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
