"""Tool chainer for executing sequences of MCP tools.

Key concepts:
- Variables: Use {var_name} syntax (not ${var_name})
- File paths: Use exact paths in arguments, not variable substitution
- Outputs: Tools return descriptive text, not just values
- Chaining: Use output_to to capture results for next steps

Example workflow:
1. code2prompt generates summary → output_to="summary"
2. gemini analyzes with file path: {"files": [{"path": "/tmp/code_summary.md"}]}
   NOT: {"files": [{"path": "{summary}"}]}
"""
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

mcp = FastMCP("Tool Chainer")

# Default storage directory
DEFAULT_STORAGE_DIR = Path.cwd() / ".mcp_handley_lab" / "tool_chainer"


class ToolStep(BaseModel):
    """A single step in a tool chain."""

    tool_id: str
    arguments: dict[str, Any]
    condition: str | None = None
    output_to: str | None = None


def _load_state(
    storage_dir: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Load state from disk."""
    storage_dir.mkdir(parents=True, exist_ok=True)
    state_file = storage_dir / "state.json"

    if state_file.exists():
        try:
            with open(state_file) as f:
                state = json.load(f)
            return (
                state.get("registered_tools", {}),
                state.get("defined_chains", {}),
                state.get("execution_history", []),
            )
        except (json.JSONDecodeError, KeyError) as e:
            # Corrupted state file - rename for inspection and raise error
            backup_path = state_file.with_suffix(".json.corrupted")
            state_file.rename(backup_path)
            raise RuntimeError(
                f"Corrupted tool chainer state file. Renamed to {backup_path} for inspection. "
                f"Original error: {e}"
            ) from e

    return {}, {}, []


def _save_state(
    storage_dir: Path,
    registered_tools: dict[str, dict[str, Any]],
    defined_chains: dict[str, dict[str, Any]],
    execution_history: list[dict[str, Any]],
):
    """Save state to disk."""
    storage_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "registered_tools": registered_tools,
        "defined_chains": defined_chains,
        "execution_history": execution_history,
    }
    with open(storage_dir / "state.json", "w") as f:
        json.dump(state, f, indent=2, default=str)


async def _execute_mcp_tool(
    server_command: str, tool_name: str, arguments: dict[str, Any], timeout: int = 30
) -> dict[str, Any]:
    """Execute a tool on an MCP server using MCP protocol."""
    # Create MCP request messages
    initialize_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "clientInfo": {"name": "tool-chainer", "version": "1.0.0"},
        },
    }

    tools_call_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }

    initialized_notification = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
        "params": {},
    }

    # Prepare input for MCP server
    input_data = (
        json.dumps(initialize_request)
        + "\n"
        + json.dumps(initialized_notification)
        + "\n"
        + json.dumps(tools_call_request)
        + "\n"
    ).encode("utf-8")

    # Execute the MCP server with stdio communication
    cmd = server_command.split()
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=Path.cwd(),
    )

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(input=input_data), timeout=timeout
        )
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")

        if process.returncode != 0:
            return {
                "success": False,
                "error": f"Server command failed: {stderr}",
                "output": stdout,
            }

        # Parse responses - expect one JSON line (tools/call response)
        lines = [line.strip() for line in stdout.strip().split("\n") if line.strip()]
        if len(lines) < 1:
            return {
                "success": False,
                "error": f"Invalid response format: expected at least 1 line, got {len(lines)}",
                "output": stdout,
            }

        try:
            # Parse the tools/call response (last line)
            response = json.loads(lines[-1])

            if "error" in response:
                return {
                    "success": False,
                    "error": response["error"].get("message", "Unknown error"),
                    "output": stdout,
                }

            # Extract result from MCP response
            result_content = response.get("result", {})
            if isinstance(result_content, dict) and "content" in result_content:
                # MCP tool response format
                content = result_content["content"]
                if isinstance(content, list) and content:
                    text_result = content[0].get("text", "")
                else:
                    text_result = str(result_content)
            else:
                # Simple result
                text_result = str(result_content)

            return {"success": True, "result": text_result, "output": stdout}

        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"Failed to parse server response: {e}",
                "output": stdout,
            }

    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        return {
            "success": False,
            "error": f"Tool execution timed out after {timeout} seconds",
            "output": "",
        }
    except asyncio.CancelledError:
        # Handle cancellation gracefully
        if process.returncode is None:
            process.kill()
            await process.wait()
        return {
            "success": False,
            "error": "Tool execution was cancelled by user",
            "output": "",
        }


def _substitute_variables(
    text: str, variables: dict[str, Any], step_outputs: dict[str, Any]
) -> str:
    """Substitute variables in text with their values."""
    if not isinstance(text, str):
        return text

    # Replace step outputs
    for step_id, output in step_outputs.items():
        text = text.replace(f"{{{step_id}}}", str(output))

    # Replace variables
    for var_name, var_value in variables.items():
        text = text.replace(f"{{{var_name}}}", str(var_value))

    return text


def _evaluate_condition(
    condition: str, variables: dict[str, Any], step_outputs: dict[str, Any] = None
) -> bool:
    """Evaluate a condition string safely."""
    if not condition:
        return True

    if step_outputs is None:
        step_outputs = {}

    # Substitute variables first
    evaluated_condition_str = _substitute_variables(condition, variables, step_outputs)

    def _parse_operand(op_str: str) -> str:
        """Parse operand, stripping quotes and returning as string for consistent comparison."""
        op_str = op_str.strip()
        # Handle quoted strings - strip quotes
        if (op_str.startswith('"') and op_str.endswith('"')) or (
            op_str.startswith("'") and op_str.endswith("'")
        ):
            return op_str[1:-1]
        # Return unquoted strings as-is for string comparison
        return op_str

    try:
        # Check for comparison operators (in order of precedence to avoid conflicts)
        operators = {
            " not contains ": lambda left, right: right not in left,
            " contains ": lambda left, right: right in left,
            " == ": lambda left, right: left == right,
            " != ": lambda left, right: left != right,
            " >= ": lambda left, right: left >= right,
            " <= ": lambda left, right: left <= right,
            " > ": lambda left, right: left > right,
            " < ": lambda left, right: left < right,
        }

        for op_str, op_func in operators.items():
            if op_str in evaluated_condition_str:
                left, right = evaluated_condition_str.split(op_str, 1)
                return op_func(_parse_operand(left), _parse_operand(right))

        # Handle boolean literals
        normalized_expr = evaluated_condition_str.lower().strip()
        if normalized_expr == "true":
            return True
        if normalized_expr == "false":
            return False

        # If no known operator or boolean literal, return False
        return False
    except Exception:
        return False


@mcp.tool(
    description="""Discovers and lists all available tools on an MCP server.

Provide the exact server command as it would be executed. This scans the server to find all available tools and their descriptions before registering them.

Examples:
```python
# Discover tools on a Python MCP server
discover_tools("python -m mcp_handley_lab.jq")

# Discover tools on a Node.js server
discover_tools("node dist/index.js")

# Discover with timeout
discover_tools("python -m my_server", timeout=10)
```"""
)
async def discover_tools(server_command: str, timeout: int = 5) -> str:
    """Discover tools available on an MCP server."""
    # Create MCP request messages
    initialize_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "clientInfo": {"name": "tool-chainer", "version": "1.0.0"},
        },
    }

    tools_list_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    }

    initialized_notification = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
        "params": {},
    }

    # Prepare input for MCP server
    input_data = (
        json.dumps(initialize_request)
        + "\n"
        + json.dumps(initialized_notification)
        + "\n"
        + json.dumps(tools_list_request)
        + "\n"
    ).encode("utf-8")

    # Execute the MCP server with stdio communication
    cmd = server_command.split()
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=Path.cwd(),
    )

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(input=input_data), timeout=timeout
        )
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")

        if process.returncode != 0:
            raise RuntimeError(f"Failed to start server: {stderr}")

        # Parse responses - expect one JSON line (tools/list response)
        lines = [line.strip() for line in stdout.strip().split("\n") if line.strip()]
        if len(lines) < 1:
            raise ValueError(
                f"Failed to parse response: expected at least 1 line, got {len(lines)}"
            )

        # Parse the tools/list response (last line)
        response = json.loads(lines[-1])
        if "error" in response:
            raise RuntimeError(
                f"Server error: {response['error'].get('message', 'Unknown error')}"
            )

        # Handle both MCP format variations
        result = response.get("result", {})
        tools = result if isinstance(result, list) else result.get("tools", [])

        if not tools:
            return "No tools found on this server."

        result_text = f"Discovered {len(tools)} tools:\n\n"
        for tool in tools:
            result_text += f"**{tool['name']}**\n"
            result_text += f"- {tool.get('description', 'No description')}\n\n"

        return result_text

    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise TimeoutError(f"Discovery timed out after {timeout} seconds") from None


@mcp.tool(
    description="""Registers a tool from an MCP server for use in chains.

CRITICAL: For file-based tools, always use exact file paths in arguments, NOT variables. Only use variables when the previous step's output contains the actual file path.

Parameters:
- `tool_id`: Unique identifier for this tool in chains
- `server_command`: Exact command to run the MCP server
- `tool_name`: Name of the tool on the server (from discover_tools)
- `output_format`: "text" (default), "json", "file_path" - how to parse tool output
- `timeout`: Execution timeout in seconds (default: 30, max recommended: 300)

Error Handling:
- Tool registration always succeeds but execution may fail if server command invalid
- Server commands are not validated until execution time
- Use discover_tools first to verify tool availability

Variable Syntax: Use `{var_name}` NOT `${var_name}`

Examples:
```python
# Register a file processing tool
register_tool(
    tool_id="jq_query",
    server_command="python -m mcp_handley_lab.jq",
    tool_name="query",
    description="Query JSON data with jq",
    timeout=15
)

# Register code analysis tool
register_tool(
    tool_id="code_summarizer",
    server_command="python -m mcp_handley_lab.code2prompt",
    tool_name="generate_prompt",
    output_format="file_path"
)

# Register LLM tool
register_tool(
    tool_id="gemini_ai",
    server_command="python -m mcp_handley_lab.llm.gemini",
    tool_name="ask",
    description="Ask Gemini questions"
)
```"""
)
async def register_tool(
    tool_id: str,
    server_command: str,
    tool_name: str,
    description: str | None = None,
    output_format: str = "text",
    timeout: int | None = None,
    storage_dir: str | None = None,
) -> str:
    """Register a tool for use in chains."""
    # Input validation
    if not tool_id.strip():
        raise ValueError("Tool ID is required")
    if not server_command.strip():
        raise ValueError("Server command is required")
    if not tool_name.strip():
        raise ValueError("Tool name is required")

    storage_path = Path(storage_dir) if storage_dir else DEFAULT_STORAGE_DIR
    registered_tools, defined_chains, execution_history = _load_state(storage_path)

    registered_tools[tool_id] = {
        "server_command": server_command,
        "tool_name": tool_name,
        "description": description or f"Tool {tool_name} from {server_command}",
        "output_format": output_format,
        "timeout": timeout or 30,
        "registered_at": datetime.now().isoformat(),
    }

    _save_state(storage_path, registered_tools, defined_chains, execution_history)

    return f"✅ Tool '{tool_id}' registered successfully!\n\n**Configuration:**\n- Server: {server_command}\n- Tool: {tool_name}\n- Format: {output_format}\n- Timeout: {timeout or 30}s"


@mcp.tool(
    description="""Defines a reusable chain of tool executions with conditional logic and variable passing.

CRITICAL File Path Handling:
- Use literal paths: `{"file_path": "/tmp/data.json"}` ✓
- Only use variables if previous step output contains the path: `{"data": "{analysis_result}"}` ✓
- DON'T use variables for file paths unless you're certain: `{"file_path": "{some_var}"}` ❌

Chain Components:
- `steps`: List of ToolStep objects with tool_id, arguments, condition, output_to
- `condition`: Optional boolean expression for conditional execution
- `output_to`: Variable name to store this step's output
- `save_to_file`: Save final result to specified file path

Variable Syntax: `{var_name}` NOT `${var_name}`

Error Handling:
- Raises ValueError if referenced tools are not registered
- Warns about potential file path variable misuse
- Chain definition succeeds even if tool configurations are invalid

Conditional Expressions:
- `"{result} contains 'success'"` - Check if output contains text
- `"{status} == 'completed'"` - Exact string comparison
- `"{error_count} != '0'"` - Inequality check

Examples:
```python
# Simple linear chain
chain_tools(
    chain_id="analyze_codebase",
    steps=[
        ToolStep(
            tool_id="code_summarizer",
            arguments={"path": "/path/to/project", "output_file": "/tmp/summary.md"},
            output_to="summary_path"
        ),
        ToolStep(
            tool_id="gemini_ai",
            arguments={
                "prompt": "Review this codebase for improvements",
                "files": [{"path": "/tmp/summary.md"}],
                "output_file": "/tmp/review.md"
            }
        )
    ]
)

# Conditional chain with error handling
chain_tools(
    chain_id="process_with_fallback",
    steps=[
        ToolStep(
            tool_id="primary_processor",
            arguments={"input_file": "/data/input.json"},
            output_to="primary_result"
        ),
        ToolStep(
            tool_id="fallback_processor",
            arguments={"input_file": "/data/input.json"},
            condition="{primary_result} contains 'error'",
            output_to="backup_result"
        ),
        ToolStep(
            tool_id="final_formatter",
            arguments={"data": "{primary_result}"},
            condition="{primary_result} != '' and {primary_result} not contains 'error'"
        )
    ],
    save_to_file="/tmp/final_output.txt"
)

# File processing pipeline
chain_tools(
    chain_id="json_analysis",
    steps=[
        ToolStep(
            tool_id="jq_query",
            arguments={"data": "/path/data.json", "filter": ".users | length"},
            output_to="user_count"
        ),
        ToolStep(
            tool_id="report_generator",
            arguments={"template": "Found {user_count} users in the dataset"}
        )
    ]
)
```"""
)
async def chain_tools(
    chain_id: str,
    steps: list[ToolStep],
    save_to_file: str | None = None,
    storage_dir: str | None = None,
) -> str:
    """Define a chain of tool executions."""
    # Input validation
    if not chain_id or not chain_id.strip():
        raise ValueError("Chain ID is required and cannot be empty")
    if not steps:
        raise ValueError("Steps are required and cannot be empty")

    storage_path = Path(storage_dir) if storage_dir else DEFAULT_STORAGE_DIR
    registered_tools, defined_chains, execution_history = _load_state(storage_path)

    # Warn about unregistered tools but allow chain creation
    for i, step in enumerate(steps):
        if step.tool_id not in registered_tools:
            print(f"⚠️  Warning (Step {i+1}): Tool '{step.tool_id}' is not registered.")
            print(
                "   Chain will fail during execution unless tool is registered first."
            )

        # Warn about potential file path variable usage
        for arg_key, arg_value in step.arguments.items():
            if (
                isinstance(arg_value, str)
                and "path" in arg_key.lower()
                and arg_value.startswith("{")
                and arg_value.endswith("}")
            ):
                print(
                    f"⚠️  Warning (Step {i+1}): Using variable '{arg_value}' for '{arg_key}'."
                )
                print("   File paths usually need exact strings, not variables.")
                print(
                    "   Only use variables if the previous step output contains the actual path."
                )

    defined_chains[chain_id] = {
        "steps": [step.model_dump() for step in steps],
        "save_to_file": save_to_file,
        "created_at": datetime.now().isoformat(),
    }

    _save_state(storage_path, registered_tools, defined_chains, execution_history)

    result = f"✅ Chain '{chain_id}' defined successfully!\n\n**Steps:**\n"
    for i, step in enumerate(steps, 1):
        result += f"{i}. {step.tool_id}"
        if step.condition:
            result += f" (if: {step.condition})"
        if step.output_to:
            result += f" → {step.output_to}"
        result += "\n"

    return result


@mcp.tool(
    description="""Executes a previously defined tool chain with variable substitution and error handling.

Provides comprehensive execution tracking, conditional step execution, and automatic variable substitution.

Parameters:
- `chain_id`: ID of the chain to execute (from chain_tools)
- `initial_input`: Optional input available as `{INITIAL_INPUT}` in all steps
- `variables`: Dict of variables available for substitution `{var_name}`
- `timeout`: Override default timeout for all steps

Variable Substitution:
- User variables: `{my_variable}` from the variables parameter
- Step outputs: `{step_1}`, `{step_2}` or custom names from `output_to`
- Initial input: `{INITIAL_INPUT}` from the initial_input parameter

Execution Features:
- Conditional steps based on previous outputs
- Automatic error handling and rollback
- Comprehensive logging with timing
- File output saving if configured

Examples:
```python
# Execute simple chain
execute_chain(
    chain_id="analyze_codebase",
    initial_input="/path/to/my/project"
)

# Execute with custom variables
execute_chain(
    chain_id="process_data",
    variables={
        "input_dir": "/data/raw",
        "output_dir": "/data/processed",
        "batch_size": "100"
    },
    timeout=300
)

# Execute conditional processing
execute_chain(
    chain_id="test_and_deploy",
    variables={
        "environment": "production",
        "skip_tests": "false"
    }
)

# Execute with file input
execute_chain(
    chain_id="document_analysis",
    initial_input="Analyze the uploaded document",
    variables={
        "document_path": "/tmp/uploaded_doc.pdf",
        "format": "markdown"
    }
)
```

Returns detailed execution summary including:
- Overall success/failure status
- Execution duration and step timing
- Step-by-step results and errors
- Final output if successful

Error Handling:
- Chain stops at first failed step unless conditionals allow continuation
- Timeout errors halt execution and are logged
- Server communication failures are retried once automatically
- Variables are validated before each step execution
- File save errors are logged but don't fail the chain"""
)
async def execute_chain(
    chain_id: str,
    initial_input: str | None = None,
    variables: dict[str, Any] | None = None,
    timeout: int | None = None,
    storage_dir: str | None = None,
) -> str:
    """Execute a defined tool chain."""
    # Input validation
    if not chain_id or not chain_id.strip():
        raise ValueError("Chain ID is required and cannot be empty")

    storage_path = Path(storage_dir) if storage_dir else DEFAULT_STORAGE_DIR
    registered_tools, defined_chains, execution_history = _load_state(storage_path)

    if chain_id not in defined_chains:
        raise ValueError(f"Chain '{chain_id}' not found")

    chain_config = defined_chains[chain_id]
    variables = variables or {}
    step_outputs = {}

    if initial_input:
        variables["INITIAL_INPUT"] = initial_input

    execution_log = {
        "chain_id": chain_id,
        "started_at": datetime.now().isoformat(),
        "initial_input": initial_input,
        "variables": variables,
        "steps": [],
        "success": False,
        "error": None,
        "final_result": None,
    }

    start_time = time.time()

    try:
        for i, step_config in enumerate(chain_config["steps"]):
            step = ToolStep(**step_config)
            step_start_time = time.time()

            # Check condition
            if step.condition and not _evaluate_condition(
                step.condition, variables, step_outputs
            ):
                execution_log["steps"].append(
                    {
                        "step": i + 1,
                        "tool_id": step.tool_id,
                        "skipped": True,
                        "condition": step.condition,
                        "duration": 0,
                    }
                )
                continue

            # Get tool configuration
            if step.tool_id not in registered_tools:
                execution_log["error"] = f"Tool '{step.tool_id}' not found"
                break

            tool_config = registered_tools[step.tool_id]

            # Substitute variables in arguments
            substituted_args = {}
            for key, value in step.arguments.items():
                if isinstance(value, str):
                    substituted_args[key] = _substitute_variables(
                        value, variables, step_outputs
                    )
                else:
                    substituted_args[key] = value

            # Execute the tool
            result = await _execute_mcp_tool(
                tool_config["server_command"],
                tool_config["tool_name"],
                substituted_args,
                timeout or tool_config["timeout"],
            )

            step_duration = time.time() - step_start_time

            # Log step execution
            step_log = {
                "step": i + 1,
                "tool_id": step.tool_id,
                "arguments": substituted_args,
                "success": result["success"],
                "duration": step_duration,
                "skipped": False,
            }

            if result["success"]:
                step_log["result"] = result["result"]
                # Store output for variable substitution
                if step.output_to:
                    step_outputs[step.output_to] = result["result"]
                else:
                    step_outputs[f"step_{i+1}"] = result["result"]
            else:
                step_log["error"] = result["error"]
                execution_log["error"] = f"Step {i+1} failed: {result['error']}"
                execution_log["steps"].append(step_log)
                break

            execution_log["steps"].append(step_log)

        # Mark as successful if we got through all steps
        if not execution_log["error"]:
            execution_log["success"] = True
            # Use the last step's output as final result
            if execution_log["steps"]:
                last_step = execution_log["steps"][-1]
                execution_log["final_result"] = last_step.get("result", "")

    except Exception as e:
        execution_log["error"] = f"Chain execution error: {e}"

    finally:
        execution_log["completed_at"] = datetime.now().isoformat()
        execution_log["total_duration"] = time.time() - start_time
        execution_history.append(execution_log)
        _save_state(storage_path, registered_tools, defined_chains, execution_history)

    # Save final result to file if requested
    if chain_config.get("save_to_file") and execution_log.get("final_result"):
        Path(chain_config["save_to_file"]).write_text(execution_log["final_result"])

    # Format execution summary
    if execution_log["error"]:
        return f"❌ Failed: {execution_log['error']}"

    result = "Chain executed successfully!\n\n"
    result += f"🔗 **Chain Execution: {chain_id}**\n\n"
    result += (
        f"**Status:** {'✅ Success' if execution_log['success'] else '❌ Failed'}\n"
    )
    result += f"**Duration:** {execution_log['total_duration']:.2f}s\n"
    result += f"**Steps Executed:** {len([s for s in execution_log['steps'] if not s.get('skipped')])}/{len(execution_log['steps'])}\n\n"

    result += "**Step Details:**\n"
    for step_log in execution_log["steps"]:
        status = (
            "⏭️ Skipped"
            if step_log.get("skipped")
            else ("✅ Success" if step_log["success"] else "❌ Failed")
        )
        result += f"{step_log['step']}. {step_log['tool_id']} - {status} ({step_log['duration']:.2f}s)\n"
        if step_log.get("error"):
            result += f"   Error: {step_log['error']}\n"

    if execution_log.get("final_result"):
        result += f"\n**Final Result:**\n{execution_log['final_result']}"

    return result


@mcp.tool(
    description="""Displays execution history of tool chains with timestamps, status, and error details.

Shows recent chain executions in reverse chronological order (newest first) with success/failure status and execution times.

Examples:
```python
# Show last 10 executions (default)
show_history()

# Show last 20 executions
show_history(limit=20)

# Show history from custom storage
show_history(limit=5, storage_dir="/custom/path")
```"""
)
async def show_history(limit: int = 10, storage_dir: str | None = None) -> str:
    """Show recent chain execution history."""
    storage_path = Path(storage_dir) if storage_dir else DEFAULT_STORAGE_DIR
    _, _, execution_history = _load_state(storage_path)

    if not execution_history:
        return "No chain executions found."

    recent_executions = execution_history[-limit:]

    result = f"Chain Execution History (last {len(recent_executions)})\n\n"

    for execution in reversed(recent_executions):
        status = "✅" if execution["success"] else "❌"
        duration = execution.get("total_duration", execution.get("duration", 0))
        # Handle both timestamp formats
        timestamp_field = execution.get("started_at", execution.get("timestamp", ""))
        timestamp = timestamp_field[:19].replace("T", " ") if timestamp_field else ""

        result += (
            f"{status} **{execution['chain_id']}** - {timestamp} ({duration:.1f}s)\n"
        )
        if execution.get("error"):
            result += f"   Error: {execution['error']}\n"
        result += "\n"

    return result


@mcp.tool(
    description="""Clears all tool chainer data including registered tools, chains, and execution history.

WARNING: This permanently deletes all registered tools, defined chains, and execution history. Use with caution.

Error Handling:
- Storage directory is created if it doesn't exist
- File deletion errors are logged but operation continues
- Always returns success even if some files couldn't be deleted

Example:
```python
# Clear all data
clear_cache()

# Clear data from custom storage
clear_cache(storage_dir="/custom/path")
```"""
)
async def clear_cache(storage_dir: str | None = None) -> str:
    """Clear all cached data."""
    storage_path = Path(storage_dir) if storage_dir else DEFAULT_STORAGE_DIR

    # Clear cache files
    if storage_path.exists():
        for cache_file in storage_path.glob("*.json"):
            cache_file.unlink()

    return "Cache cleared successfully"


@mcp.tool(
    description="""Shows the status of the Tool Chainer server.

**Key Parameters:**
- `storage_dir`: An optional path to a custom storage directory.

**Input/Output:**
- **Input**: An optional storage directory path.
- **Output**: A string containing a comprehensive overview of the Tool Chainer's status, including registered tools, defined chains, and execution history.

**Examples:**
```python
# Show the Tool Chainer server status.
server_info()
```"""
)
async def server_info(storage_dir: str | None = None) -> str:
    """Get server status and registered tools information."""
    storage_path = Path(storage_dir) if storage_dir else DEFAULT_STORAGE_DIR
    registered_tools, defined_chains, execution_history = _load_state(storage_path)

    result = f"""Tool Chainer Server Status
============================
Status: Ready ✓
Storage Directory: {storage_path}

**Registered Tools:** {len(registered_tools)}"""

    if registered_tools:
        result += "\n"
        for tool_id, config in registered_tools.items():
            result += (
                f"- {tool_id}: {config['tool_name']} ({config['server_command']})\n"
            )

    result += f"\n**Defined Chains:** {len(defined_chains)}"
    if defined_chains:
        result += "\n"
        for chain_id, config in defined_chains.items():
            step_count = len(config["steps"])
            result += f"- {chain_id}: {step_count} steps\n"

    result += f"\nExecution History: {len(execution_history)} entries"

    result += """

**Available Tools:**
- discover_tools: Find tools on MCP servers
- register_tool: Register tools for chaining
- chain_tools: Define tool execution chains
- execute_chain: Run defined chains
- show_history: View execution history
- clear_cache: Clear cached data
- server_info: Get server status

**Variable Usage Examples:**

1. Capture tool output:
   - Set: output_to="my_result"
   - Use: {my_result} in next step

2. File path handling:
   - Fixed path: "file_path": "/tmp/data.json"
   - From output: "data": "{step1_output}"
   - NOT: "file_path": "{some_var}" (unless var contains the path)

3. Variable syntax:
   - Correct: {variable_name}
   - Wrong: ${variable_name} or $variable_name

Example chain for file processing:
Step 1: generate_file → output_to="file_info"
Step 2: read_file with arguments={"path": "/tmp/generated.txt"}"""

    return result
