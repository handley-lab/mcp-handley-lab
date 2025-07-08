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
        # First tier: tools and options with proper ordering using tags
        local -a tools options option_descs

        # Define tags and their display order
        _tags tools options
        compstate[group-order]=(tools options)

        # Get available tools dynamically
        tools=($(mcp-cli --list-tools 2>/dev/null | awk '/^  [a-zA-Z]/ {print $1}'))

        # Define options and their descriptions separately
        options=(
            '--help'
            '--list-tools'
            '--config'
            '--init-config'
            '--install-completion'
            '--show-completion'
        )
        option_descs=(
            'Show help message'
            'List all available tools'
            'Show configuration file location'
            'Create default configuration file'
            'Install zsh completion script'
            'Show completion installation instructions'
        )

        # Add tools first (no descriptions needed for tools)
        compadd -J 'available tools' -t tools -a tools

        # Add options with descriptions
        compadd -J 'global options' -t options -d option_descs -- $options
        return 0
    elif [[ $CURRENT -eq 3 && $words[2] && $words[2] != -* ]]; then
        # Second tier: functions and tool options with proper ordering
        local tool=$words[2]
        local -a functions options option_descs

        # Define tags and their display order
        _tags functions options
        compstate[group-order]=(functions options)

        # Get functions for the selected tool
        functions=($(mcp-cli $tool --help 2>/dev/null | awk '/^FUNCTIONS$/,/^$/ {if (/^    [a-zA-Z]/) {gsub(/^    /, ""); print $1}}'))

        # Tool-level options and descriptions
        options=(
            '--help'
            '--json-output'
            '--params-from-json'
        )
        option_descs=(
            'Show help for this tool'
            'Output in JSON format'
            'Load parameters from JSON file'
        )

        # Add functions first (no descriptions needed for functions)
        compadd -J 'available functions' -t functions -a functions

        # Add options with descriptions
        compadd -J 'tool options' -t options -d option_descs -- $options
        return 0
    elif [[ $CURRENT -gt 3 && $words[2] && $words[2] != -* && $words[3] && $words[3] != -* ]]; then
        # Third tier: parameters and function options with proper ordering
        local tool=$words[2]
        local function=$words[3]
        local -a params options option_descs

        # Define tags and their display order
        _tags parameters options
        compstate[group-order]=(parameters options)

        # Get parameter names for the function
        params=($(mcp-cli $tool $function --help 2>/dev/null | awk '/^OPTIONS$/,/^$/ {if (/^    [a-zA-Z]/) {gsub(/^    /, ""); print $1 "="}}'))

        # Function-level options and descriptions
        options=(
            '--help'
            '--json-output'
            '--params-from-json'
        )
        option_descs=(
            'Show detailed help for this function'
            'Output in JSON format'
            'Load parameters from JSON file'
        )

        # Add parameters first (no descriptions needed for parameters)
        compadd -J 'function parameters' -t parameters -a params

        # Add options with descriptions
        compadd -J 'function options' -t options -d option_descs -- $options
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
