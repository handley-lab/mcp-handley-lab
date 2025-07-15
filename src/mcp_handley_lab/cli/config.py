"""Configuration management for MCP CLI."""

import os
from pathlib import Path
from typing import Any

import click
import tomllib


def get_config_dir() -> Path:
    """Get the configuration directory for MCP CLI."""
    if config_home := os.getenv("XDG_CONFIG_HOME"):
        return Path(config_home) / "mcp"
    return Path.home() / ".config" / "mcp"


def get_config_file() -> Path:
    """Get the configuration file path."""
    return get_config_dir() / "config.toml"


def load_config() -> dict[str, Any]:
    """Load configuration from file."""
    config_file = get_config_file()
    with open(config_file, "rb") as f:
        return tomllib.load(f)


def create_default_config():
    """Create a default configuration file."""
    config_file = get_config_file()
    config_dir = config_file.parent

    # Create config directory if it doesn't exist
    config_dir.mkdir(parents=True, exist_ok=True)

    # Default configuration
    default_config = """# MCP CLI Configuration

[aliases]
# Tool aliases for common shortcuts
# notes = "knowledge-tool"
# code = "jq"

[defaults]
# Default models for LLM providers
# gemini_model = "gemini-2.5-pro"
# openai_model = "gpt-4o"
# claude_model = "claude-3-5-sonnet-20240620"

# Default output format: "human" or "json"
output_format = "human"

# Default file output behavior
# output_file = "-"  # stdout by default
"""

    if not config_file.exists():
        with open(config_file, "w") as f:
            f.write(default_config)
        click.echo(f"Created default configuration at: {config_file}")
    else:
        click.echo(f"Configuration file already exists at: {config_file}")
