"""Tool chainer for executing sequences of MCP tools."""
import json
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Tool Chainer")

# Default storage directory
DEFAULT_STORAGE_DIR = Path.cwd() / ".mcp_handley_lab" / "tool_chainer"


class ToolStep(BaseModel):
    """A single step in a tool chain."""
    tool_id: str
    arguments: Dict[str, Any]
    condition: Optional[str] = None
    output_to: Optional[str] = None


def _load_state(storage_dir: Path) -> tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
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
                state.get("execution_history", [])
            )
        except (json.JSONDecodeError, KeyError):
            pass
    
    return {}, {}, []


def _save_state(storage_dir: Path, registered_tools: Dict[str, Dict[str, Any]], 
                defined_chains: Dict[str, Dict[str, Any]], execution_history: List[Dict[str, Any]]):
    """Save state to disk."""
    storage_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "registered_tools": registered_tools,
        "defined_chains": defined_chains,
        "execution_history": execution_history
    }
    with open(storage_dir / "state.json", "w") as f:
        json.dump(state, f, indent=2, default=str)


def _execute_mcp_tool(server_command: str, tool_name: str, arguments: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
    """Execute a tool on an MCP server."""
    # Create a temporary input file with the request
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(request, f)
        input_file = f.name
    
    try:
        # Execute the MCP server command
        cmd = server_command.split() + [input_file]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=Path.cwd()
        )
        
        if result.returncode != 0:
            return {
                "success": False,
                "error": f"Server command failed: {result.stderr}",
                "output": result.stdout
            }
        
        # Parse the response
        try:
            response = json.loads(result.stdout)
            if "error" in response:
                return {
                    "success": False,
                    "error": response["error"].get("message", "Unknown error"),
                    "output": result.stdout
                }
            
            return {
                "success": True,
                "result": response.get("result", {}).get("content", [{}])[0].get("text", ""),
                "output": result.stdout
            }
        except json.JSONDecodeError:
            return {
                "success": True,
                "result": result.stdout,
                "output": result.stdout
            }
    
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Tool execution timed out after {timeout} seconds",
            "output": ""
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Execution error: {e}",
            "output": ""
        }
    finally:
        # Clean up temp file
        try:
            Path(input_file).unlink()
        except:
            pass


def _substitute_variables(text: str, variables: Dict[str, Any], step_outputs: Dict[str, Any]) -> str:
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


def _evaluate_condition(condition: str, variables: Dict[str, Any], step_outputs: Dict[str, Any]) -> bool:
    """Evaluate a condition string."""
    if not condition:
        return True
    
    # Substitute variables first
    condition = _substitute_variables(condition, variables, step_outputs)
    
    # Simple condition evaluation (could be expanded)
    try:
        # Basic comparison operators
        if " == " in condition:
            left, right = condition.split(" == ", 1)
            return left.strip().strip("'\"") == right.strip().strip("'\"")
        elif " != " in condition:
            left, right = condition.split(" != ", 1)
            return left.strip().strip("'\"") != right.strip().strip("'\"")
        elif " contains " in condition:
            left, right = condition.split(" contains ", 1)
            return right.strip().strip("'\"") in left.strip().strip("'\"")
        else:
            # Try to evaluate as boolean expression
            return bool(eval(condition))
    except:
        return False




@mcp.tool(description="Discovers available tools from a specified MCP server command.")
def discover_tools(server_command: str, timeout: int = 5) -> str:
    """Discover tools available on an MCP server."""
    try:
        # Create tools/list request
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(request, f)
            input_file = f.name
        
        try:
            cmd = server_command.split() + [input_file]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=Path.cwd()
            )
            
            if result.returncode != 0:
                return f"❌ Failed to connect to server: {result.stderr}"
            
            # Parse response
            response = json.loads(result.stdout)
            if "error" in response:
                return f"❌ Server error: {response['error'].get('message', 'Unknown error')}"
            
            tools = response.get("result", {}).get("tools", [])
            
            if not tools:
                return "No tools found on this server."
            
            result_text = f"🔧 **Discovered {len(tools)} tools:**\n\n"
            for tool in tools:
                result_text += f"**{tool['name']}**\n"
                result_text += f"- {tool.get('description', 'No description')}\n\n"
            
            return result_text
            
        finally:
            Path(input_file).unlink()
            
    except subprocess.TimeoutExpired:
        return f"❌ Server discovery timed out after {timeout} seconds"
    except Exception as e:
        return f"❌ Discovery error: {e}"


@mcp.tool(description="Registers a specific tool from an MCP server, making it available for chaining.")
def register_tool(
    tool_id: str,
    server_command: str,
    tool_name: str,
    description: Optional[str] = None,
    output_format: str = "text",
    timeout: Optional[int] = None,
    storage_dir: Optional[str] = None
) -> str:
    """Register a tool for use in chains."""
    storage_path = Path(storage_dir) if storage_dir else DEFAULT_STORAGE_DIR
    registered_tools, defined_chains, execution_history = _load_state(storage_path)
    
    registered_tools[tool_id] = {
        "server_command": server_command,
        "tool_name": tool_name,
        "description": description or f"Tool {tool_name} from {server_command}",
        "output_format": output_format,
        "timeout": timeout or 30,
        "registered_at": datetime.now().isoformat()
    }
    
    _save_state(storage_path, registered_tools, defined_chains, execution_history)
    
    return f"✅ Tool '{tool_id}' registered successfully!\n\n**Configuration:**\n- Server: {server_command}\n- Tool: {tool_name}\n- Format: {output_format}\n- Timeout: {timeout or 30}s"


@mcp.tool(description="Defines a sequential chain of registered tools.")
def chain_tools(
    chain_id: str,
    steps: List[ToolStep],
    save_to_file: Optional[str] = None,
    storage_dir: Optional[str] = None
) -> str:
    """Define a chain of tool executions."""
    storage_path = Path(storage_dir) if storage_dir else DEFAULT_STORAGE_DIR
    registered_tools, defined_chains, execution_history = _load_state(storage_path)
    
    # Validate that all referenced tools are registered
    for step in steps:
        if step.tool_id not in registered_tools:
            raise ValueError(f"Tool '{step.tool_id}' is not registered. Register it first with register_tool().")
    
    defined_chains[chain_id] = {
        "steps": [step.model_dump() for step in steps],
        "save_to_file": save_to_file,
        "created_at": datetime.now().isoformat()
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


@mcp.tool(description="Executes a defined chain with an initial input and optional variables.")
def execute_chain(
    chain_id: str,
    initial_input: Optional[str] = None,
    variables: Optional[Dict[str, Any]] = None,
    timeout: Optional[int] = None,
    storage_dir: Optional[str] = None
) -> str:
    """Execute a defined tool chain."""
    storage_path = Path(storage_dir) if storage_dir else DEFAULT_STORAGE_DIR
    registered_tools, defined_chains, execution_history = _load_state(storage_path)
    
    if chain_id not in defined_chains:
        raise ValueError(f"Chain '{chain_id}' not found. Define it first with chain_tools().")
    
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
        "final_result": None
    }
    
    start_time = time.time()
    
    try:
        for i, step_config in enumerate(chain_config["steps"]):
            step = ToolStep(**step_config)
            step_start_time = time.time()
            
            # Check condition
            if step.condition and not _evaluate_condition(step.condition, variables, step_outputs):
                execution_log["steps"].append({
                    "step": i + 1,
                    "tool_id": step.tool_id,
                    "skipped": True,
                    "condition": step.condition,
                    "duration": 0
                })
                continue
            
            # Get tool configuration
            if step.tool_id not in registered_tools:
                raise ValueError(f"Tool '{step.tool_id}' not registered")
            
            tool_config = registered_tools[step.tool_id]
            
            # Substitute variables in arguments
            substituted_args = {}
            for key, value in step.arguments.items():
                if isinstance(value, str):
                    substituted_args[key] = _substitute_variables(value, variables, step_outputs)
                else:
                    substituted_args[key] = value
            
            # Execute the tool
            result = _execute_mcp_tool(
                tool_config["server_command"],
                tool_config["tool_name"],
                substituted_args,
                timeout or tool_config["timeout"]
            )
            
            step_duration = time.time() - step_start_time
            
            # Log step execution
            step_log = {
                "step": i + 1,
                "tool_id": step.tool_id,
                "arguments": substituted_args,
                "success": result["success"],
                "duration": step_duration,
                "skipped": False
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
        try:
            Path(chain_config["save_to_file"]).write_text(execution_log["final_result"])
        except Exception as e:
            execution_log["save_error"] = f"Failed to save to file: {e}"
    
    # Format execution summary
    result = f"🔗 **Chain Execution: {chain_id}**\n\n"
    result += f"**Status:** {'✅ Success' if execution_log['success'] else '❌ Failed'}\n"
    result += f"**Duration:** {execution_log['total_duration']:.2f}s\n"
    result += f"**Steps Executed:** {len([s for s in execution_log['steps'] if not s.get('skipped')])}/{len(execution_log['steps'])}\n\n"
    
    if execution_log["error"]:
        result += f"**Error:** {execution_log['error']}\n\n"
    
    result += "**Step Details:**\n"
    for step_log in execution_log["steps"]:
        status = "⏭️ Skipped" if step_log.get("skipped") else ("✅ Success" if step_log["success"] else "❌ Failed")
        result += f"{step_log['step']}. {step_log['tool_id']} - {status} ({step_log['duration']:.2f}s)\n"
        if step_log.get("error"):
            result += f"   Error: {step_log['error']}\n"
    
    if execution_log.get("final_result"):
        result += f"\n**Final Result:**\n{execution_log['final_result']}"
    
    return result


@mcp.tool(description="Displays the execution history of recent chains.")
def show_history(limit: int = 10, storage_dir: Optional[str] = None) -> str:
    """Show recent chain execution history."""
    storage_path = Path(storage_dir) if storage_dir else DEFAULT_STORAGE_DIR
    _, _, execution_history = _load_state(storage_path)
    
    if not execution_history:
        return "No chain executions found."
    
    recent_executions = execution_history[-limit:]
    
    result = f"📚 **Chain Execution History** (last {len(recent_executions)})\n\n"
    
    for execution in reversed(recent_executions):
        status = "✅" if execution["success"] else "❌"
        duration = execution.get("total_duration", 0)
        timestamp = execution["started_at"][:19].replace("T", " ")
        
        result += f"{status} **{execution['chain_id']}** - {timestamp} ({duration:.1f}s)\n"
        if execution.get("error"):
            result += f"   Error: {execution['error']}\n"
        result += "\n"
    
    return result


@mcp.tool(description="Clears all cached results and execution history.")
def clear_cache(storage_dir: Optional[str] = None) -> str:
    """Clear all cached data."""
    storage_path = Path(storage_dir) if storage_dir else DEFAULT_STORAGE_DIR
    
    # Clear cache files
    for cache_file in storage_path.glob("*.json"):
        cache_file.unlink()
    
    # Save empty state
    _save_state(storage_path, {}, {}, [])
    
    return "✅ Cache and execution history cleared successfully!"


@mcp.tool(description="Shows the status of the tool chainer, including registered tools.")
def server_info(storage_dir: Optional[str] = None) -> str:
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
            result += f"- {tool_id}: {config['tool_name']} ({config['server_command']})\n"
    
    result += f"\n**Defined Chains:** {len(defined_chains)}"
    if defined_chains:
        result += "\n"
        for chain_id, config in defined_chains.items():
            step_count = len(config['steps'])
            result += f"- {chain_id}: {step_count} steps\n"
    
    result += f"\n**Execution History:** {len(execution_history)} executions"
    
    result += """

Available tools:
- discover_tools: Find tools on MCP servers
- register_tool: Register tools for chaining
- chain_tools: Define tool execution chains
- execute_chain: Run defined chains
- show_history: View execution history
- clear_cache: Clear cached data
- server_info: Get server status"""
    
    return result