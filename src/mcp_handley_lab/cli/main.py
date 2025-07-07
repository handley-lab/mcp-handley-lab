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

    # Simplified parameter parsing
    positional_args = [p for p in params if "=" not in p]
    kwargs.update(dict(p.split("=", 1) for p in params if "=" in p))

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
