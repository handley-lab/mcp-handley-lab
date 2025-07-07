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
        # Completing first argument (tool name)
        _arguments -C \\
            '(--help)--help[Show help message]' \\
            '(--list-tools)--list-tools[List all available tools]' \\
            '(--config)--config[Show configuration file location]' \\
            '(--init-config)--init-config[Create default configuration file]' \\
            '(--install-completion)--install-completion[Install zsh completion script]' \\
            '(--show-completion)--show-completion[Show completion installation instructions]' \\
            '1:tool:->tools' \\
            && return 0
    elif [[ $CURRENT -eq 3 && $words[2] && $words[2] != -* ]]; then
        # Completing second argument (function name) when tool is specified
        _arguments -C \\
            '(--help)--help[Show help for this tool]' \\
            '(--json-output)--json-output[Output in JSON format]' \\
            '(--params-from-json)--params-from-json[Load parameters from JSON file]:file:_files' \\
            '2:function:->functions' \\
            '*:params:->params' \\
            && return 0
    elif [[ $CURRENT -gt 3 && $words[2] && $words[2] != -* && $words[3] && $words[3] != -* ]]; then
        # Completing parameters when both tool and function are specified
        _arguments -C \\
            '(--help)--help[Show detailed help for this function]' \\
            '(--json-output)--json-output[Output in JSON format]' \\
            '(--params-from-json)--params-from-json[Load parameters from JSON file]:file:_files' \\
            '*:params:->params' \\
            && return 0
    else
        # Fallback to global options
        _arguments -C \\
            '(--help)--help[Show help message]' \\
            '(--list-tools)--list-tools[List all available tools]' \\
            '(--config)--config[Show configuration file location]' \\
            '(--init-config)--init-config[Create default configuration file]' \\
            '(--install-completion)--install-completion[Install zsh completion script]' \\
            '(--show-completion)--show-completion[Show completion installation instructions]' \\
            '1:tool:->tools' \\
            && return 0
    fi

    case $state in
        tools)
            # Get available tools - parse the actual output format
            tools=($(mcp-cli --list-tools 2>/dev/null | awk '/^  [a-zA-Z]/ {print $1}'))
            _describe 'tools' tools
            ;;
        functions)
            # Get functions for the selected tool
            local tool=$words[2]
            if [[ -n $tool ]]; then
                # Parse the "Available functions:" section from tool help
                local functions=($(mcp-cli $tool --help 2>/dev/null | awk '/Available functions:/,/^$/ {if (/^  [a-zA-Z]/) print $1}'))
                _describe 'functions' functions
            fi
            ;;
        params)
            # For now, just complete filenames for parameters
            _files
            ;;
    esac
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
