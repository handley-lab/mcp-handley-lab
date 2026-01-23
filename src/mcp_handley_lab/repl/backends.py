"""Backend definitions for REPL sessions.

Each backend specifies the command to launch the REPL and the sentinel style
to use for detecting command completion.
"""

from dataclasses import dataclass
from enum import Enum


class SentinelStyle(Enum):
    """How to detect command completion for different backends."""

    SHELL = "shell"  # Use echo $? after command
    PYTHON = "python"  # Use print() statements


@dataclass
class BackendConfig:
    """Configuration for a REPL backend."""

    name: str
    command: list[str]
    sentinel_style: SentinelStyle
    description: str


BACKENDS: dict[str, BackendConfig] = {
    "bash": BackendConfig(
        name="bash",
        command=["bash", "--norc", "--noprofile"],
        sentinel_style=SentinelStyle.SHELL,
        description="Bash shell without rc files for clean environment",
    ),
    "ipython": BackendConfig(
        name="ipython",
        command=["ipython", "--simple-prompt", "--colors=NoColor", "--no-banner"],
        sentinel_style=SentinelStyle.PYTHON,
        description="IPython with simplified output for parsing",
    ),
    "python": BackendConfig(
        name="python",
        command=["python3", "-u"],  # Unbuffered output
        sentinel_style=SentinelStyle.PYTHON,
        description="Standard Python interpreter",
    ),
}


def get_backend(name: str) -> BackendConfig:
    """Get backend configuration by name.

    Raises:
        ValueError: If backend name is not recognized.
    """
    if name not in BACKENDS:
        available = ", ".join(BACKENDS.keys())
        raise ValueError(f"Unknown backend '{name}'. Available: {available}")
    return BACKENDS[name]


def list_backends() -> list[dict]:
    """List all available backends."""
    return [
        {"name": cfg.name, "description": cfg.description}
        for cfg in BACKENDS.values()
    ]
