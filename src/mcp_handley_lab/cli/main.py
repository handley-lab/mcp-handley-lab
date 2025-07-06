"""Main CLI implementation using Click framework."""
import json
import sys
from typing import Dict, Any, Optional
import click

from .discovery import get_tool_with_aliases, get_available_tools, get_tool_info
from .rpc_client import get_tool_client, cleanup_clients
from .config import get_config_file, create_default_config, get_default_output_format
from .completion import install_completion_script, show_completion_install




@click.command(add_help_option=False)
@click.argument("tool_name", required=False)
@click.argument("function_name", required=False)
@click.argument("params", nargs=-1)
@click.option("--list-tools", is_flag=True, help="List all available tools")
@click.option("--list-functions", is_flag=True, help="List functions for this tool")
@click.option("--help-function", metavar="FUNCTION", help="Show help for a specific function")
@click.option("--help", is_flag=True, help="Show help message")
@click.option("--json-output", is_flag=True, help="Output in JSON format")
@click.option("--params-from-json", type=click.File('r'), help="Load parameters from JSON file")
@click.option("--config", help="Show configuration file location", is_flag=True)
@click.option("--init-config", help="Create default configuration file", is_flag=True)
@click.option("--install-completion", help="Install zsh completion script", is_flag=True)
@click.option("--show-completion", help="Show completion installation instructions", is_flag=True)
@click.pass_context
def cli(ctx, tool_name, function_name, params, list_tools, list_functions, help_function, help, json_output, params_from_json, config, init_config, install_completion, show_completion):
    """MCP CLI - Unified command-line interface for MCP tools.
    
    Examples:
      mcp-cli --list-tools                    # List available tools
      mcp-cli jq --help                       # Show help for jq tool
      mcp-cli jq --list-functions             # List functions in jq tool  
      mcp-cli jq --help-function query        # Show help for jq query function
      mcp-cli jq query data='{"x":1}'         # Run jq query function
    """
    
    # Handle global configuration options first
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
    
    # Handle global list tools option
    if list_tools:
        list_all_tools()
        ctx.exit()
    
    # Handle help flag
    if help:
        if tool_name:
            # Tool-specific help
            show_tool_help(tool_name)
        else:
            # Global help
            click.echo(ctx.get_help())
        ctx.exit()
    
    # If no tool provided, show help
    if not tool_name:
        click.echo(ctx.get_help())
        ctx.exit()
    
    # Handle tool-specific options
    if list_functions:
        list_tool_functions(tool_name)
        ctx.exit()
    
    if help_function:
        show_function_details(tool_name, help_function)
        ctx.exit()
    
    # Require function name for execution
    if not function_name:
        click.echo(f"Usage: mcp-cli {tool_name} <function> [params...]", err=True)
        click.echo(f"Use 'mcp-cli {tool_name} --list-functions' to see available functions.", err=True)
        ctx.exit(1)
    
    # Execute tool function
    run_tool_function(ctx, tool_name, function_name, params, json_output, params_from_json)


def list_all_tools():
    """List all available tools."""
    # Just list tool names without introspection for speed
    available_tools = get_available_tools()
    
    click.echo("Available tools:")
    for tool_name in sorted(available_tools.keys()):
        click.echo(f"  {tool_name}")
    
    # Note: aliases would require config loading, skip for speed
    click.echo(f"\nTotal: {len(available_tools)} tools")
    click.echo("Use 'mcp-cli <tool> --list-functions' to see available functions.")


def list_tool_functions(tool_name):
    """List functions available in a tool."""
    tools = get_tool_with_aliases()
    
    if tool_name not in tools:
        click.echo(f"Tool '{tool_name}' not found. Use 'mcp-cli --list-tools' to see available tools.", err=True)
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
    
    click.echo(f"\nUse 'mcp-cli {tool_name} --help-function <function>' for parameter details.")


def show_tool_help(tool_name):
    """Show comprehensive help for a specific tool."""
    available_tools = get_available_tools()
    
    if tool_name not in available_tools:
        click.echo(f"Tool '{tool_name}' not found. Available tools: {', '.join(available_tools.keys())}", err=True)
        return
    
    command = available_tools[tool_name]
    tool_info = get_tool_info(tool_name, command)
    
    if not tool_info:
        click.echo(f"Failed to introspect tool '{tool_name}'")
        return
    
    functions = tool_info.get("functions", {})
    
    # Show tool header
    click.echo(f"MCP CLI - {tool_name} tool")
    click.echo("=" * (len(f"MCP CLI - {tool_name} tool")))
    click.echo()
    
    # Show tool usage
    click.echo("Usage:")
    click.echo(f"  mcp-cli {tool_name} --list-functions           # List available functions")
    click.echo(f"  mcp-cli {tool_name} --help-function FUNC      # Show help for specific function")
    click.echo(f"  mcp-cli {tool_name} FUNCTION [params...]      # Execute a function")
    click.echo()
    
    # Show available functions
    if functions:
        click.echo("Available functions:")
        for func_name, func_info in sorted(functions.items()):
            description = func_info.get("description", "No description")
            # Truncate long descriptions
            if len(description) > 80:
                description = description[:77] + "..."
            click.echo(f"  {func_name:<20} {description}")
        click.echo()
        
        click.echo("Examples:")
        # Show examples for first few functions
        example_functions = list(functions.items())[:2]
        for func_name, func_info in example_functions:
            input_schema = func_info.get('inputSchema', {})
            properties = input_schema.get('properties', {})
            required = input_schema.get('required', [])
            
            if required:
                # Show example with first required parameter
                param_name = required[0]
                click.echo(f"  mcp-cli {tool_name} {func_name} {param_name}=<value>")
            else:
                click.echo(f"  mcp-cli {tool_name} {func_name}")
        
        click.echo()
        click.echo(f"For detailed parameter information, use:")
        click.echo(f"  mcp-cli {tool_name} --help-function <function_name>")
    else:
        click.echo("No functions available for this tool.")


def show_function_details(tool_name, function_name):
    """Show detailed information about a specific function."""
    available_tools = get_available_tools()
    
    if tool_name not in available_tools:
        click.echo(f"Tool '{tool_name}' not found. Available tools: {', '.join(available_tools.keys())}", err=True)
        return
    
    command = available_tools[tool_name]
    tool_info = get_tool_info(tool_name, command)
    
    if not tool_info:
        click.echo(f"Failed to introspect tool '{tool_name}'")
        return
    
    functions = tool_info.get("functions", {})
    if function_name not in functions:
        click.echo(f"Function '{function_name}' not found in {tool_name}. Available: {', '.join(functions.keys())}", err=True)
        return
    
    func_info = functions[function_name]
    click.echo(f"Function: {function_name}")
    click.echo(f"Description: {func_info.get('description', 'No description')}")
    
    # Show parameters
    input_schema = func_info.get('inputSchema', {})
    properties = input_schema.get('properties', {})
    required = input_schema.get('required', [])
    
    if properties:
        click.echo("\nParameters:")
        for param_name, param_info in properties.items():
            required_mark = " (required)" if param_name in required else ""
            param_type = param_info.get('type', 'any')
            default = param_info.get('default')
            description = param_info.get('description', 'No description')
            
            click.echo(f"  --{param_name}{required_mark}")
            click.echo(f"    Type: {param_type}")
            if default is not None:
                click.echo(f"    Default: {default}")
            click.echo(f"    Description: {description}")
    else:
        click.echo("\nNo parameters required.")
        
    # Show usage example
    click.echo(f"\nUsage:")
    if properties:
        example_params = []
        for param_name, param_info in list(properties.items())[:2]:  # Show first 2 params
            if param_name in required:
                example_params.append(f"{param_name}=<value>")
        param_str = " " + " ".join(example_params) if example_params else ""
        click.echo(f"  mcp-cli {tool_name} {function_name}{param_str}")
    else:
        click.echo(f"  mcp-cli {tool_name} {function_name}")


# Register cleanup on exit
import atexit
atexit.register(cleanup_clients)


def run_tool_function(ctx, tool_name, function_name, params, json_output, params_from_json):
    """Run a tool function."""
    
    # Get available tools
    available_tools = get_available_tools()
    if tool_name not in available_tools:
        click.echo(f"Tool '{tool_name}' not found. Available tools: {', '.join(available_tools.keys())}", err=True)
        ctx.exit(1)
    
    command = available_tools[tool_name]
    
    # Get tool info and validate function
    try:
        tool_info = get_tool_info(tool_name, command)
        if not tool_info:
            click.echo(f"Failed to introspect tool '{tool_name}'", err=True)
            ctx.exit(1)
        
        functions = tool_info.get("functions", {})
        if function_name not in functions:
            available_functions = list(functions.keys())
            click.echo(f"Function '{function_name}' not found in {tool_name}. Available: {', '.join(available_functions)}", err=True)
            ctx.exit(1)
        
        # Parse parameters
        kwargs = {}
        if params_from_json:
            kwargs = json.load(params_from_json)
        
        # Get function schema for parameter mapping
        function_schema = functions[function_name]
        input_schema = function_schema.get("inputSchema", {})
        properties = input_schema.get("properties", {})
        required_params = input_schema.get("required", [])
        
        # Parse command line params
        positional_args = []
        for param in params:
            if "=" in param:
                # Named parameter: key=value format
                key, value = param.split("=", 1)
                kwargs[key] = value
            else:
                # Positional argument
                positional_args.append(param)
        
        # Map positional arguments to parameters (required first, then optional)
        if positional_args:
            # Create ordered parameter list: required first, then optional
            param_order = required_params + [p for p in properties.keys() if p not in required_params]
            
            for i, value in enumerate(positional_args):
                if i < len(param_order):
                    param_name = param_order[i]
                    # Only assign if not already set by named parameter
                    if param_name not in kwargs:
                        kwargs[param_name] = value
        
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
                    # Extract text content for human-readable output
                    if isinstance(result, dict) and "content" in result:
                        content = result["content"]
                        if isinstance(content, list) and len(content) > 0:
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




if __name__ == "__main__":
    cli()