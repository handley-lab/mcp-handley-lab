# **Section 1: Logical API & Tool Specification**

## **High-Level Framework Purpose**

The framework is a comprehensive, multi-purpose toolkit designed to bridge various external services and local command-line utilities into a unified API accessible via the Model Context Protocol (MCP). Its primary function is to provide a cohesive set of tools for a developer-centric AI assistant, enabling complex workflows that involve:

*   **Code & Git Interaction:** Analyzing, summarizing, and diffing codebases.
*   **AI Model Integration:** Accessing and managing interactions with multiple Large Language Model (LLM) providers (Google Gemini, OpenAI).
*   **Productivity & Scheduling:** Managing Google Calendar events, calendars, and scheduling.
*   **Data Manipulation:** Querying, editing, and validating JSON data structures.
*   **Interactive Editing:** Programmatically invoking a `vim` session for user-driven content editing and refinement.
*   **Workflow Automation:** Chaining the framework's own tools together to create sophisticated, multi-step automated tasks.
*   **Persistent Memory:** Creating and managing "agents" with persistent conversational memory for stateful interactions with LLMs.

## **Complete Tool Inventory**

The framework exposes the following core tools:

1.  **code2prompt:** Wraps the `code2prompt` CLI to analyze and summarize codebases.
2.  **google_calendar:** Provides full-featured integration with the Google Calendar API.
3.  **jq:** Wraps the `jq` CLI for powerful JSON manipulation.
4.  **llm (gemini & openai):** A suite of tools for interacting with Google Gemini and OpenAI models, including text generation, image analysis, and stateful agent management.
5.  **tool_chainer:** A meta-tool for discovering, registering, and executing chains of other tools within the framework.
6.  **vim:** An interactive tool to open a `vim` editor session for user input and content modification.

---

## **Detailed Tool Schemas & Method Descriptions**

### 1. Code2Prompt Tool

**Tool Description:** Wraps the `code2prompt` CLI tool to generate structured prompts from codebases for AI analysis.

| Method Name | Description | Input Parameters | Return Value |
| :--- | :--- | :--- | :--- |
| `generate_prompt` | Creates a structured, token-counted summary of a codebase and saves it to a file. Returns the output path for large-scale analysis. | <ul><li>`path` (string, required): The absolute or relative path to the codebase directory.</li><li>`output_file` (string, optional): Path for the output file. A temporary file is used if omitted.</li><li>`include` (array[string], optional): Glob patterns to include (e.g., `['*.py']`).</li><li>`exclude` (array[string], optional): Glob patterns to exclude (e.g., `['node_modules']`).</li><li>`output_format` (string, optional): Output format. Enum: `markdown`, `json`, `xml`. Default: `markdown`.</li><li>`line_numbers` (boolean, optional): Add line numbers to source code. Default: `false`.</li><li>`full_directory_tree` (boolean, optional): Include the full directory tree. Default: `false`.</li><li>`follow_symlinks` (boolean, optional): Follow symbolic links. Default: `false`.</li><li>`hidden` (boolean, optional): Include hidden files and directories. Default: `false`.</li><li>`no_codeblock` (boolean, optional): Disable markdown code block wrapping. Default: `false`.</li><li>`absolute_paths` (boolean, optional): Use absolute instead of relative paths. Default: `false`.</li><li>`encoding` (string, optional): Tokenizer to use. Enum: `cl100k`, `p50k`, `p50k_edit`, `r50k`, `gpt2`. Default: `cl100k`.</li><li>`tokens` (string, optional): Token count format. Enum: `raw`, `format`. Default: `format`.</li><li>`sort` (string, optional): File sorting order. Enum: `name_asc`, `name_desc`, `date_asc`, `date_desc`. Default: `name_asc`.</li></ul> | A string containing a success message with the path to the generated output file and its size. |
| `analyze_codebase` | Performs a quick analysis of a codebase directory, returning a text-based directory tree and token count. | <ul><li>`path` (string, required): Path to the codebase directory.</li><li>`include` (array[string], optional): Patterns to include.</li><li>`exclude` (array[string], optional): Patterns to exclude.</li><li>`hidden` (boolean, optional): Include hidden files. Default: `false`.</li><li>`encoding` (string, optional): Tokenizer for token counting. Enum: `cl100k`, `p50k`, `p50k_edit`, `r50k`, `gpt2`. Default: `cl100k`.</li></ul> | A string containing a formatted analysis of the codebase structure and token count. |
| `git_diff` | Generates a structured text representation of git changes (staged or between commits) from a local repository path. | <ul><li>`path` (string, required): Path to the git repository.</li><li>`mode` (string, optional): Type of diff. Enum: `diff`, `branch_diff`, `branch_log`. Default: `diff`.</li><li>`branch1` (string, optional): First branch for comparison.</li><li>`branch2` (string, optional): Second branch for comparison.</li><li>`include` (array[string], optional): Patterns to include.</li><li>`exclude` (array[string], optional): Patterns to exclude.</li></ul> | A string containing a success message with the path to the generated diff output file. |
| `server_info` | Checks the status of the code2prompt server and verifies that the CLI tool is installed and available. | None | A string containing a formatted status report, including CLI version and available tools. |

### 2. Google Calendar Tool

**Tool Description:** Provides comprehensive Google Calendar operations including management of events, calendars, attendees, and sharing.

| Method Name | Description | Input Parameters | Return Value |
| :--- | :--- | :--- | :--- |
| `list_events` | Lists calendar events within a date range. | <ul><li>`calendar_id` (string, optional): Calendar name or ID. Defaults to "primary".</li><li>`start_date` (string, optional): Start date (YYYY-MM-DD).</li><li>`end_date` (string, optional): End date (YYYY-MM-DD).</li><li>`max_results` (integer, optional): Max events to return. Default: 100.</li></ul> | A formatted string listing the events found, including their title, start time, and ID. |
| `get_event` | Retrieves a single calendar event by its ID. | <ul><li>`event_id` (string, required): The ID of the event to retrieve.</li><li>`calendar_id` (string, optional): Calendar name or ID. Defaults to "primary".</li></ul> | A formatted string with detailed information about the event, including title, time, description, location, and attendees. |
| `create_event` | Creates a new event in a specified calendar. | <ul><li>`summary` (string, required): The title of the event.</li><li>`start_datetime` (string, required): Start time in ISO format or YYYY-MM-DD.</li><li>`end_datetime` (string, required): End time in ISO format or YYYY-MM-DD.</li><li>`description` (string, optional): The event description.</li><li>`calendar_id` (string, optional): Target calendar name or ID. Defaults to "primary".</li><li>`timezone` (string, optional): Timezone for the event. Default: "UTC".</li><li>`attendees` (array[string], optional): List of attendee email addresses.</li></ul> | A formatted string confirming the event creation with its title, time, and ID. |
| `update_event` | Updates an existing calendar event. | <ul><li>`event_summary` (string, required): The current summary of the event for safety validation.</li><li>`event_id` (string, required): The ID of the event to update.</li><li>`calendar_id` (string, optional): Calendar name or ID. Defaults to "primary".</li><li>`summary` (string, optional): New event title.</li><li>`start_datetime` (string, optional): New start time in ISO format.</li><li>`end_datetime` (string, optional): New end time in ISO format.</li><li>`description` (string, optional): New event description.</li></ul> | A formatted string confirming the event update and listing the fields that were changed. |
| `delete_event` | Deletes a calendar event. | <ul><li>`event_summary` (string, required): The summary of the event to be deleted for safety validation.</li><li>`event_id` (string, required): The ID of the event to delete.</li><li>`calendar_id` (string, optional): Calendar name or ID. Defaults to "primary".</li></ul> | A formatted string confirming the permanent deletion of the event. |
| `list_calendars` | Lists all available calendars with their IDs and access levels. | None | A formatted string listing all accessible calendars, including their name, ID, access role, and color. |
| `find_time` | Finds available free time slots in a calendar. | <ul><li>`calendar_id` (string, optional): Calendar name or ID. Defaults to "primary".</li><li>`start_date` (string, optional): Search start date (YYYY-MM-DD).</li><li>`end_date` (string, optional): Search end date (YYYY-MM-DD).</li><li>`duration_minutes` (integer, optional): Required slot duration in minutes. Default: 60.</li><li>`work_hours_only` (boolean, optional): Limit search to 9-17 local time. Default: `true`.</li></ul> | A formatted string listing available time slots that match the criteria. |
| `server_info` | Gets the status of the Google Calendar server and connection. | None | A string indicating whether the server is connected and ready, or an error message if not. |

### 3. JQ Tool

**Tool Description:** Provides JSON querying, editing, and manipulation capabilities using the `jq` command-line tool.

| Method Name | Description | Input Parameters | Return Value |
| :--- | :--- | :--- | :--- |
| `query` | Queries JSON data from a string or file using a jq filter expression. | <ul><li>`data` (string, required): JSON data as a string or a file path.</li><li>`filter` (string, optional): The jq filter expression to apply. Default: `.` (identity).</li><li>`compact` (boolean, optional): Output compact JSON. Default: `false`.</li><li>`raw_output` (boolean, optional): Output raw strings instead of JSON-quoted text. Default: `false`.</li></ul> | The result of the jq query as a string. |
| `edit` | Edits a JSON file in-place using a jq transformation filter. | <ul><li>`file_path` (string, required): Path to the JSON file to edit.</li><li>`filter` (string, required): jq transformation expression (e.g., `.name = "new"`).</li><li>`backup` (boolean, optional): Create a backup file before editing. Default: `true`.</li></ul> | A string confirming the file was edited successfully, including the path to the backup if created. |
| `read` | Reads and pretty-prints a JSON file, with an optional filter. | <ul><li>`file_path` (string, required): Path to the JSON file to read.</li><li>`filter` (string, optional): Optional jq filter to apply. Default: `.`</li></ul> | The content of the JSON file as a formatted string. |
| `validate` | Validates the syntax of JSON data from a string or file. | <ul><li>`data` (string, required): JSON data as a string or a file path.</li></ul> | A string confirming that the JSON is valid, or an error if it is invalid. |
| `format` | Pretty-prints or compacts JSON data from a string or file. | <ul><li>`data` (string, required): JSON data as a string or a file path.</li><li>`compact` (boolean, optional): Output compact JSON. Default: `false`.</li><li>`sort_keys` (boolean, optional): Sort object keys alphabetically. Default: `false`.</li></ul> | The formatted JSON data as a string. |
| `server_info` | Gets the status of the JQ server and `jq` CLI availability. | None | A string containing a formatted status report, including the `jq` version and available tools. |

### 4. LLM Tool (Gemini & OpenAI)

**Tool Description:** A suite of tools for interacting with Google Gemini and OpenAI models, including stateful agent management.

| Method Name | Provider | Description | Input Parameters | Return Value |
| :--- | :--- | :--- | :--- | :--- |
| `ask` | Gemini | Asks a question to a Gemini model. Supports file analysis, search grounding, and persistent memory via agents. | <ul><li>`prompt` (string, required): The question or task.</li><li>`agent_name` (string, optional): Named agent for conversation memory.</li><li>`model` (string, optional): Model to use (`flash`, `pro`). Default: `flash`.</li><li>`temperature` (float, optional): Response randomness (0.0-1.0). Default: 0.7.</li><li>`grounding` (boolean, optional): Use Google Search for real-time info. Default: `false`.</li><li>`files` (array, optional): List of files to analyze (string content, or dicts with `path`/`content`).</li></ul> | The text response from the Gemini model, appended with usage and cost information. |
| `analyze_image` | Gemini | Analyzes one or more images with a prompt using Gemini's vision model. | <ul><li>`prompt` (string, required): The question about the image(s).</li><li>`image_data` (string, optional): A single base64-encoded image.</li><li>`images` (array, optional): List of image dicts (with `path` or `data` keys).</li><li>`focus` (string, optional): Focus for analysis (`general`, `text`, `technical`, `comparison`). Default: `general`.</li><li>`model` (string, optional): Vision model to use. Default: `pro`.</li><li>`agent_name` (string, optional): Named agent for conversation memory.</li></ul> | A text analysis of the image(s), appended with usage and cost information. |
| `generate_image` | Gemini | Generates an image from a text prompt using the Imagen model. | <ul><li>`prompt` (string, required): The text description for the image.</li><li>`model` (string, optional): Image model to use (`image`, `image-flash`). Default: `image`.</li><li>`agent_name` (string, optional): Named agent for memory.</li></ul> | A string containing a success message with the path to the saved image file and cost info. |
| `create_agent` | Gemini | Creates a new named agent for persistent conversation memory. | <ul><li>`agent_name` (string, required): A unique name for the agent.</li><li>`personality` (string, optional): A description of the agent's personality or role.</li></ul> | A string confirming the creation of the agent. |
| `list_agents` | Gemini | Lists all existing named agents and their summary statistics. | None | A formatted string listing all agents with their stats (creation date, message count, cost, etc.). |
| `agent_stats` | Gemini | Retrieves detailed statistics and history for a specific named agent. | <ul><li>`agent_name` (string, required): The name of the agent.</li></ul> | A detailed string report of the agent's statistics. |
| `clear_agent` | Gemini | Clears the conversation history of a named agent. | <ul><li>`agent_name` (string, required): The name of the agent to clear.</li></ul> | A string confirming that the agent's history has been cleared. |
| `delete_agent` | Gemini | Permanently deletes a named agent and all its data. | <ul><li>`agent_name` (string, required): The name of the agent to delete.</li></ul> | A string confirming the permanent deletion of the agent. |
| `server_info` | Gemini | Checks the Gemini server status and API key configuration. | None | A formatted string report of the server's status and configuration. |
| `ask` | OpenAI | Asks a question to an OpenAI GPT model. Supports file analysis. | <ul><li>`prompt` (string, required): The question or task.</li><li>`agent_name` (string, optional): Named agent for memory.</li><li>`model` (string, optional): Model to use (`gpt-4o`, `o1`, etc.). Default: `gpt-4o`.</li><li>`temperature` (float, optional): Response randomness (0.0-2.0). Default: 0.7.</li><li>`max_tokens` (integer, optional): Maximum tokens in the response.</li><li>`files` (array, optional): List of files to analyze (string content, or dicts with `path`/`content`).</li></ul> | The text response from the OpenAI model, appended with usage and cost information. |
| `analyze_image` | OpenAI | Analyzes one or more images with a prompt using a GPT vision model. | <ul><li>`prompt` (string, required): The question about the image(s).</li><li>`image_data` (string, optional): A single base64-encoded image.</li><li>`images` (array, optional): List of image dicts (with `path` or `data` keys).</li><li>`focus` (string, optional): Focus for analysis. Default: `general`.</li><li>`model` (string, optional): Vision model to use. Default: `gpt-4o`.</li><li>`agent_name` (string, optional): Named agent for memory.</li></ul> | A text analysis of the image(s), appended with usage and cost information. |
| `generate_image` | OpenAI | Generates an image from a text prompt using a DALL-E model. | <ul><li>`prompt` (string, required): The text description for the image.</li><li>`model` (string, optional): DALL-E model to use (`dall-e-3`, `dall-e-2`). Default: `dall-e-3`.</li><li>`quality` (string, optional): Image quality (`standard`, `hd`). Default: `standard`.</li><li>`size` (string, optional): Image dimensions. Default: `1024x1024`.</li><li>`agent_name` (string, optional): Named agent for memory.</li></ul> | A string containing a success message with the path to the saved image file and cost info. |
| `server_info` | OpenAI | Checks the OpenAI server status and API key configuration. | None | A formatted string report of the server's status and configuration. |

### 5. Tool Chainer Tool

**Tool Description:** A meta-tool that enables discovering, registering, and executing chains of other MCP tools.

| Method Name | Description | Input Parameters | Return Value |
| :--- | :--- | :--- | :--- |
| `discover_tools` | Discovers available tools from a specified MCP server command. | <ul><li>`server_command` (string, required): The command to run the target MCP server (e.g., `python -m mcp_handley_lab.llm.gemini.server`).</li><li>`timeout` (integer, optional): Timeout in seconds. Default: 5.</li></ul> | A formatted string listing the names and descriptions of tools found on the target server. |
| `register_tool` | Registers a specific tool from an MCP server, making it available for chaining. | <ul><li>`tool_id` (string, required): A unique ID to assign to this tool for chaining.</li><li>`server_command` (string, required): The command to run the tool's server.</li><li>`tool_name` (string, required): The actual name of the tool on its server.</li><li>`description` (string, optional): A description for this registered tool.</li><li>`output_format` (string, optional): The expected format of the tool's output. Default: `text`.</li><li>`timeout` (integer, optional): Execution timeout in seconds.</li></ul> | A string confirming the successful registration of the tool with its configuration details. |
| `chain_tools` | Defines a sequential chain of registered tools. | <ul><li>`chain_id` (string, required): A unique ID for the chain.</li><li>`steps` (array[object], required): A list of steps, where each step is an object with `tool_id`, `arguments`, optional `condition`, and optional `output_to`.</li><li>`save_to_file` (string, optional): Path to save the final result of the chain.</li></ul> | A string confirming the chain was defined successfully and listing its steps. |
| `execute_chain` | Executes a defined chain with an initial input and optional variables. | <ul><li>`chain_id` (string, required): The ID of the chain to execute.</li><li>`initial_input` (string, optional): The initial input value, available as `{INITIAL_INPUT}`.</li><li>`variables` (object, optional): A dictionary of custom variables available as `{VAR_NAME}`.</li><li>`timeout` (integer, optional): An overall timeout for the chain execution.</li></ul> | A detailed string summarizing the chain execution, including step-by-step status, duration, and the final result. |
| `show_history` | Displays the execution history of recent chains. | <ul><li>`limit` (integer, optional): The number of recent executions to show. Default: 10.</li></ul> | A formatted string listing recent chain executions with their ID, timestamp, and duration. |
| `clear_cache` | Clears all cached results and execution history. | None | A string confirming that the cache and history have been cleared. |
| `server_info` | Shows the status of the tool chainer, including registered tools. | None | A formatted string report of the server's status, including counts of registered tools and executed chains. |

### 6. Vim Tool

**Tool Description:** Provides interactive text editing using `vim` and tracks user modifications.

| Method Name | Description | Input Parameters | Return Value |
| :--- | :--- | :--- | :--- |
| `prompt_user_edit` | Creates a temporary file, opens `vim` for user editing, and returns the changes. | <ul><li>`content` (string, required): The initial content to be edited.</li><li>`file_extension` (string, optional): File extension for syntax highlighting. Default: `.txt`.</li><li>`instructions` (string, optional): Instructions displayed as comments in the file.</li><li>`show_diff` (boolean, optional): If `true`, returns a diff of the changes. Default: `true`.</li><li>`keep_file` (boolean, optional): If `true`, preserves the temporary file. Default: `false`.</li></ul> | A string containing either a summary of changes (lines added/removed and a diff) or the full edited content, based on `show_diff`. |
| `quick_edit` | Opens `vim` for creating new content from scratch. | <ul><li>`file_extension` (string, optional): File extension for syntax highlighting. Default: `.txt`.</li><li>`instructions` (string, optional): Instructions for the editing task.</li><li>`initial_content` (string, optional): Optional starting content.</li></ul> | A string containing the final content created by the user. |
| `open_file` | Opens an existing local file in `vim` for editing. | <ul><li>`file_path` (string, required): The path to the local file to open.</li><li>`instructions` (string, optional): Instructions to display.</li><li>`show_diff` (boolean, optional): If `true`, returns a diff of the changes. Default: `true`.</li><li>`backup` (boolean, optional): If `true`, creates a backup of the original file. Default: `true`.</li></ul> | A string containing either a summary of changes (diff) or a confirmation message, along with the backup file path if created. |
| `server_info` | Gets the status of the Vim server and `vim` CLI availability. | None | A string containing a formatted status report, including the `vim` version and available tools. |

---

# **Section 2: Rewrite & Implementation Strategy using the Python SDK**

## **Architectural Recommendations**

### **Project & Directory Structure**

The new project should follow a modern, scalable structure that separates concerns and promotes maintainability. I recommend a `src`-based layout:

```txt
mcp-framework-rewrite/
├── pyproject.toml         # Project metadata, dependencies (uv or poetry)
├── README.md
├── .env.example           # Example environment variables
├── src/
│   └── mcp_framework/
│       ├── __init__.py
│       ├── common/          # Shared utilities
│       │   ├── __init__.py
│       │   ├── config.py      # Pydantic settings for API keys, etc.
│       │   ├── memory.py      # AgentMemory system
│       │   └── pricing.py     # Cost tracking logic
│       │
│       ├── code2prompt/
│       │   ├── __init__.py
│       │   └── tool.py        # Implements code2prompt tools
│       │
│       ├── google_calendar/
│       │   ├── __init__.py
│       │   └── tool.py        # Implements calendar tools
│       │
│       ├── jq/
│       │   ├── __init__.py
│       │   └── tool.py        # Implements jq tools
│       │
│       ├── llm/
│       │   ├── __init__.py
│       │   ├── gemini.py      # Implements Gemini tools
│       │   └── openai.py      # Implements OpenAI tools
│       │
│       ├── tool_chainer/
│       │   ├── __init__.py
│       │   └── tool.py        # Implements tool chainer
│       │
│       └── vim/
│           ├── __init__.py
│           └── tool.py        # Implements vim tools
│
└── tests/                   # Unit and integration tests
    ├── test_code2prompt.py
    ├── test_google_calendar.py
    └── ...
```

### **Logical Grouping**

*   **One Tool, One Module:** Each logical tool from Section 1 (`code2prompt`, `google_calendar`, etc.) should be implemented in its own Python module (e.g., `src/mcp_framework/google_calendar/tool.py`).
*   **Central `FastMCP` Instance per Tool:** Each module will define its own `FastMCP` instance. This isolates tools and makes them independently testable and deployable. For example, in `google_calendar/tool.py`:
    ```python
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("Google Calendar")
    ```
*   **Shared Utilities:** Logic that is shared across tools, such as configuration loading (`BaseSettings`), the `AgentMemory` class, and cost tracking, should reside in the `src/mcp_framework/common/` directory to avoid code duplication.

## **Mapping Legacy API to the Modern SDK**

The rewrite should fully embrace the `FastMCP` high-level framework provided by the SDK, which simplifies development significantly compared to the legacy approach.

*   **Embrace Decorators and Type Hinting:** All API methods identified in Section 1 must be implemented as Python functions decorated with `@mcp.tool()`. The SDK will automatically generate the `inputSchema` from Python type hints. This eliminates the need for manual `schemas.yml` files.

    *   **Example (Legacy `jq/schemas.yml`):**
        ```yml
        query:
          description: Queries JSON data...
          inputSchema:
            type: object
            properties:
              data:
                type: string
                description: JSON data as a string or a file path.
        ```

    *   **New Implementation (`jq/tool.py`):**
        ```python
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("JQ Tool")

        @mcp.tool(description="Queries JSON data from a string or file using a jq filter expression.")
        def query(data: str, filter: str = ".") -> str:
            # Implementation logic here...
            return "jq result"
        ```

*   **Use `FastMCP` for Server Logic:** Each tool module will create and use a `FastMCP` instance. This replaces the manual request handling, dispatch tables, and JSON-RPC response formatting seen in the legacy `MCPServer` base class.

    *   **Legacy:** `self.tool_handlers = {"list_events": self._handle_list_events, ...}`
    *   **New:** The `@mcp.tool` decorator handles all dispatching. The function name becomes the tool name.

*   **Pydantic for Complex Data:** For tools that accept complex structured data (like the `files` parameter in LLM tools or `steps` in `tool_chainer`), define Pydantic models. `FastMCP` seamlessly integrates with Pydantic for validation and serialization.

    *   **Example for `tool_chainer`:**
        ```python
        from pydantic import BaseModel
        from typing import List, Dict, Any

        class ToolStep(BaseModel):
            tool_id: str
            arguments: Dict[str, Any]
            condition: str | None = None
            output_to: str | None = None

        @mcp.tool
        def chain_tools(chain_id: str, steps: List[ToolStep]):
            # 'steps' will be a list of validated Pydantic objects
            ...
        ```

## **Key Implementation Considerations for the Contractor**

1.  **Configuration Management:**
    *   **Recommendation:** Continue using `pydantic-settings` as seen in the modern legacy files. Create a `config.py` in the `common` directory to define a `BaseSettings` class for all API keys (`GEMINI_API_KEY`, `OPENAI_API_KEY`), file paths (`GOOGLE_CALENDAR_CREDENTIALS_FILE`), and other environment-specific settings.
    *   **Example (`common/config.py`):**
        ```python
        from pydantic_settings import BaseSettings

        class Settings(BaseSettings):
            gemini_api_key: str = "YOUR_API_KEY_HERE"
            openai_api_key: str = "YOUR_API_KEY_HERE"
            google_credentials_file: str = "~/.google_calendar_credentials.json"
            google_token_file: str = "~/.google_calendar_token.json"

            class Config:
                env_file = ".env"
                env_file_encoding = "utf-8"

        settings = Settings()
        ```
    *   Each tool module can then import the global `settings` object.

2.  **Error Handling:**
    *   **Recommendation:** The `FastMCP` framework automatically catches exceptions and converts them into standard MCP error responses. The developer should use standard, specific Python exceptions within the tool functions.
    *   **Idiomatic Approach:**
        *   Raise `ValueError` for invalid arguments.
        *   Raise `FileNotFoundError` for missing files.
        *   Raise `ConnectionError` for failed API calls to external services.
        *   Raise `PermissionError` for filesystem access issues.
        *   Avoid generic `Exception` or `RuntimeError`. The framework will handle the rest.
    *   **Example:**
        ```python
        @mcp.tool
        def read(file_path: str) -> str:
            if not os.path.exists(file_path):
                # This will be automatically sent to the client as an MCP error.
                raise FileNotFoundError(f"The file '{file_path}' does not exist.")
            # ... implementation
        ```

3.  **Data Modeling:**
    *   **Recommendation:** Use Pydantic `BaseModel` for any non-primitive data structures passed into or returned from tools. This provides strong validation and clear schemas.
    *   For the `google_calendar` tool, create Pydantic models for `Event`, `Attendee`, etc., to structure the data returned from the Google API before formatting it into a string for the user. This makes the code cleaner and easier to test.

## **Suggested Development Roadmap**

This roadmap provides a logical sequence for building the framework, starting with foundations and moving to more complex components.

1.  **Phase 1: Project Setup & Foundations**
    *   **Step 1:** Create the project directory structure as recommended above. Initialize it as a `uv` or `poetry` project.
    *   **Step 2:** Implement the `common/config.py` module for centralized settings management using `pydantic-settings`.
    *   **Step 3:** Add initial dependencies to `pyproject.toml` (`mcp`, `pydantic`, `pydantic-settings`).

2.  **Phase 2: Simple, Self-Contained Tools**
    *   **Step 4: Implement the `jq` tool.** This tool has no external Python dependencies and is a great way to establish the basic pattern: create a `FastMCP` instance, define `@mcp.tool`-decorated functions that wrap a CLI, and write corresponding unit tests.
    *   **Step 5: Implement the `vim` tool.** This is another CLI-based tool that will solidify the pattern for interacting with subprocesses.

3.  **Phase 3: External API Integrations**
    *   **Step 6: Implement the `google_calendar` tool.** This is a critical step that involves handling OAuth2 authentication. The logic for token storage and refresh from the legacy code can be adapted but should be placed within this tool's module. Ensure all methods from Section 1 are implemented. Write tests that mock the Google API client.
    *   **Step 7: Implement the `llm` tools (`gemini` & `openai`).**
        *   First, implement the shared `common/memory.py` and `common/pricing.py` modules.
        *   Implement `gemini.py` and `openai.py` with their respective `ask`, `analyze_image`, and `generate_image` tools.
        *   Integrate the `AgentMemory` system into the `gemini` tools (`create_agent`, `list_agents`, etc.).

4.  **Phase 4: Complex & Meta Tools**
    *   **Step 8: Implement the `code2prompt` tool.** This combines file system interaction with CLI wrapping.
    *   **Step 9: Implement the `tool_chainer` tool.** This is the most complex component. It will need to dynamically call other MCP servers via `subprocess`. Use the logic from the legacy implementation as a guide but refactor it to be cleaner and more robust. Define Pydantic models for the chain and step structures.

5.  **Phase 5: Testing & Finalization**
    *   **Step 10: Write Comprehensive Unit & Integration Tests.** For each tool, ensure there are unit tests that mock external dependencies (APIs, CLIs) and integration tests that verify the tools work together where applicable.
    *   **Step 11:** Create a top-level `README.md` for the new project, documenting setup, configuration, and how to run each tool server.
    *   **Step 12:** Final review of the entire codebase for adherence to modern Python best practices (e.g., code style with `ruff` or `black`, clear docstrings).
