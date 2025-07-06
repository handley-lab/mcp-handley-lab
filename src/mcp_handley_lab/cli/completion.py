"""Shell completion support for MCP CLI."""
import click
from pathlib import Path


def install_completion_script():
    """Install zsh completion script."""
    
    zsh_completion = '''#compdef mcp-cli

_mcp_cli() {
    local context state line
    local -a commands
    
    # Get the completion from Click
    eval "$(_MCP_CLI_COMPLETE=zsh_complete mcp-cli)"
}

_mcp_cli "$@"
'''
    
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
    click.echo("  eval \"$(_MCP_CLI_COMPLETE=zsh_source mcp-cli)\"")
    click.echo("")
    click.echo("For Bash:")
    click.echo("  eval \"$(_MCP_CLI_COMPLETE=bash_source mcp-cli)\"")
    click.echo("")
    click.echo("Add the appropriate line to your shell's configuration file.")
    click.echo("Or run 'mcp-cli --install-completion' to install zsh completion permanently.")