"""Main CLI implementation using Click framework."""
import json
import sys
import signal
from typing import Dict, Any, Optional
import click

from .discovery import get_tool_with_aliases, get_function_schema, validate_tool_and_function
from .rpc_client import get_tool_client, cleanup_clients
from .config import get_config_file, create_default_config, get_default_output_format
from .completion import install_completion_script, show_completion_install


def cleanup_handler(signum, frame):
    """Handle cleanup on exit."""
    cleanup_clients()
    sys.exit(0)


# Register cleanup handlers
signal.signal(signal.SIGINT, cleanup_handler)
signal.signal(signal.SIGTERM, cleanup_handler)


def convert_cli_value(value: str, param_type: str) -> Any:
    """Convert CLI string value to appropriate Python type."""
    if param_type in ["integer", "int"]:
        return int(value)
    elif param_type in ["number", "float"]:
        return float(value)
    elif param_type in ["boolean", "bool"]:
        return value.lower() in ("true", "1", "yes", "on")
    elif param_type == "array" or value.startswith("["):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            # If JSON parsing fails, treat as list of strings
            return [v.strip() for v in value.split(",")]
    elif param_type == "object" or value.startswith("{"):
        return json.loads(value)
    else:
        return value


def create_click_option(param_name: str, param_schema: Dict[str, Any]) -> click.Option:
    """Create a Click option from a parameter schema."""
    param_type = param_schema.get("type", "string")
    description = param_schema.get("description", "")
    default = param_schema.get("default")
    required = param_schema.get("required", False) and default is None
    
    # Handle arrays with multiple flag
    multiple = param_type == "array"
    
    # Create the option
    option_names = [f"--{param_name}"]
    
    # Add short option for common parameters
    short_options = {
        "output_file": "-o",
        "file": "-f",
        "format": "-F",
        "verbose": "-v",
        "help": "-h"
    }
    if param_name in short_options:
        option_names.insert(0, short_options[param_name])
    
    return click.Option(
        option_names,
        default=default,
        required=required,
        help=description,
        multiple=multiple,
        type=str  # Always accept as string, convert later
    )


def create_dynamic_command(tool_name: str, function_name: str, function_schema: Dict[str, Any], tool_info: Dict[str, Any]) -> click.Command:
    """Create a dynamic Click command from a function schema."""
    
    @click.command(
        name=function_name,
        help=function_schema.get("description", f"Execute {function_name} function")
    )
    @click.option(
        "--json-output", 
        is_flag=True, 
        help="Output in JSON format"
    )
    @click.option(
        "--params-from-json",
        type=click.File('r'),
        help="Load parameters from JSON file"
    )
    @click.pass_context
    def dynamic_command(ctx, json_output, params_from_json, **kwargs):
        """Dynamic command implementation."""
        try:
            # Get the actual command (handle aliases)
            command = tool_info["command"]
            actual_tool_name = tool_info["name"]
            
            # Load parameters from JSON file if provided
            if params_from_json:
                try:
                    json_params = json.load(params_from_json)
                    # Merge with CLI arguments (CLI takes precedence)
                    for key, value in kwargs.items():
                        if value is not None:
                            json_params[key] = value
                    kwargs = json_params
                except json.JSONDecodeError as e:
                    click.echo(f"Error parsing JSON file: {e}", err=True)
                    ctx.exit(1)
            
            # Convert parameters based on schema
            converted_params = {}
            input_schema = function_schema.get("inputSchema", {})
            properties = input_schema.get("properties", {})
            
            for param_name, value in kwargs.items():
                if value is None:
                    continue
                    
                param_schema = properties.get(param_name, {})
                param_type = param_schema.get("type", "string")
                
                try:
                    # Handle multiple values (arrays)
                    if isinstance(value, tuple):
                        if param_type == "array":
                            converted_params[param_name] = list(value)
                        else:
                            # Use the last value for non-array parameters
                            converted_params[param_name] = convert_cli_value(value[-1], param_type)
                    else:
                        converted_params[param_name] = convert_cli_value(str(value), param_type)
                except (ValueError, json.JSONDecodeError) as e:
                    click.echo(f"Error converting parameter {param_name}: {e}", err=True)
                    ctx.exit(1)
            
            # Get tool client and make the call
            client = get_tool_client(actual_tool_name, command)
            response = client.call_tool(function_name, converted_params)
            
            if response is None:
                click.echo(f"Failed to execute {function_name}", err=True)
                ctx.exit(1)
            
            # Handle response
            if response.get("jsonrpc") == "2.0":
                if "error" in response:
                    error = response["error"]
                    click.echo(f"Error: {error.get('message', 'Unknown error')}", err=True)
                    if "data" in error:
                        click.echo(f"Details: {error['data']}", err=True)
                    ctx.exit(1)
                else:
                    result = response.get("result", {})
                    
                    # Format output
                    if json_output or get_default_output_format() == "json":
                        click.echo(json.dumps(result, indent=2))
                    else:
                        # Extract text content for human-readable output
                        if isinstance(result, dict) and "content" in result:
                            content = result["content"]
                            if isinstance(content, list) and len(content) > 0:
                                # Extract text from content array
                                text_parts = []
                                for item in content:
                                    if isinstance(item, dict) and item.get("type") == "text":
                                        text_parts.append(item.get("text", ""))
                                if text_parts:
                                    click.echo("\n".join(text_parts))
                                else:
                                    click.echo(json.dumps(result, indent=2))
                            else:
                                click.echo(str(content))
                        else:
                            click.echo(str(result))
            else:
                click.echo(str(response))
                
        except Exception as e:
            click.echo(f"Unexpected error: {e}", err=True)
            ctx.exit(1)
    
    # Add parameters from schema
    input_schema = function_schema.get("inputSchema", {})
    properties = input_schema.get("properties", {})
    required_params = input_schema.get("required", [])
    
    for param_name, param_schema in properties.items():
        # Mark as required if in required list and no default
        param_schema = param_schema.copy()
        if param_name in required_params and "default" not in param_schema:
            param_schema["required"] = True
        
        option = create_click_option(param_name, param_schema)
        dynamic_command.params.append(option)
    
    return dynamic_command


@click.group()
@click.option("--config", help="Show configuration file location", is_flag=True)
@click.option("--init-config", help="Create default configuration file", is_flag=True)
@click.option("--install-completion", help="Install zsh completion script", is_flag=True)
@click.option("--show-completion", help="Show completion installation instructions", is_flag=True)
@click.pass_context
def cli(ctx, config, init_config, install_completion, show_completion):
    """MCP CLI - Unified command-line interface for MCP tools."""
    
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
    
    # Ensure cleanup on exit
    ctx.ensure_object(dict)


@cli.command()
def list_tools():
    """List all available tools."""
    tools = get_tool_with_aliases()
    
    click.echo("Available tools:")
    for tool_name, tool_info in sorted(tools.items()):
        if tool_info.get("is_alias"):
            click.echo(f"  {tool_name} -> {tool_info['target_tool']} (alias)")
        else:
            click.echo(f"  {tool_name}")


@cli.command()
@click.argument("tool_name")
def list_functions(tool_name):
    """List functions available in a tool."""
    tools = get_tool_with_aliases()
    
    if tool_name not in tools:
        click.echo(f"Tool '{tool_name}' not found. Use 'mcp-cli list-tools' to see available tools.", err=True)
        return
    
    tool_info = tools[tool_name]
    functions = tool_info.get("functions", {})
    
    if not functions:
        click.echo(f"No functions found for tool '{tool_name}'")
        return
    
    click.echo(f"Functions in {tool_name}:")
    for func_name, func_info in sorted(functions.items()):
        description = func_info.get("description", "No description")
        click.echo(f"  {func_name} - {description}")


# Register cleanup on exit
import atexit
atexit.register(cleanup_clients)


if __name__ == "__main__":
    # Dynamically discover and add tools
    tools = get_tool_with_aliases()
    
    for tool_name, tool_info in tools.items():
        # Create a group for each tool
        tool_group = click.Group(
            name=tool_name,
            help=f"Commands for {tool_name} tool"
        )
        
        # Add functions as commands
        functions = tool_info.get("functions", {})
        for func_name, func_schema in functions.items():
            cmd = create_dynamic_command(tool_name, func_name, func_schema, tool_info)
            tool_group.add_command(cmd)
        
        # Add the tool group to main CLI
        cli.add_command(tool_group)
    
    # Enable shell completion
    cli()
else:
    # For when imported as module, ensure dynamic commands are loaded
    tools = get_tool_with_aliases()
    
    for tool_name, tool_info in tools.items():
        tool_group = click.Group(
            name=tool_name,
            help=f"Commands for {tool_name} tool"
        )
        
        functions = tool_info.get("functions", {})
        for func_name, func_schema in functions.items():
            cmd = create_dynamic_command(tool_name, func_name, func_schema, tool_info)
            tool_group.add_command(cmd)
        
        cli.add_command(tool_group)