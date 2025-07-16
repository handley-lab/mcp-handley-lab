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
