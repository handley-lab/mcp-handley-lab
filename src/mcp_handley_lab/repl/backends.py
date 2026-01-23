"""Backend definitions for REPL sessions.

Each backend specifies the command to launch the REPL and the prompt regex
to use for detecting command completion.
"""

from dataclasses import dataclass


@dataclass
class BackendConfig:
    """Configuration for a REPL backend."""

    name: str
    command: list[str]
    description: str
    prompt_regex: str  # Regex matching the prompt
    continuation_regex: str | None = None  # For multi-line (e.g., "... ")
    supports_bracketed_paste: bool = True
    echo_commands: bool = True  # Does REPL echo sent input?


BACKENDS: dict[str, BackendConfig] = {
    "bash": BackendConfig(
        name="bash",
        command=["bash", "--norc", "--noprofile"],
        description="Bash shell without rc files for clean environment",
        # Match common bash prompts: "$", "$ ", "bash-5.3$", "bash-5.3$ ", etc.
        prompt_regex=r"^.*\$ ?$",
    ),
    "python": BackendConfig(
        name="python",
        command=["python3", "-u"],  # Unbuffered output
        description="Standard Python interpreter",
        prompt_regex=r"^>>> ?$",
        continuation_regex=r"^\.\.\.",  # Matches any line starting with "..."
    ),
    "ipython": BackendConfig(
        name="ipython",
        command=["ipython", "--simple-prompt", "--colors=NoColor", "--no-banner"],
        description="IPython with simplified output for parsing",
        prompt_regex=r"^In \[\d+\]: ?$",
        continuation_regex=r"^   \.\.\.:",  # Matches any line starting with "   ...:"
    ),
    "aichat": BackendConfig(
        name="aichat",
        command=["aichat", "--session", "mcp"],
        description="aichat LLM interface",
        prompt_regex=r"^> ?$",
        echo_commands=False,
    ),
    "ollama": BackendConfig(
        name="ollama",
        command=["ollama", "run", "llama3"],
        description="Ollama LLM",
        prompt_regex=r"^>>> ?$",
        echo_commands=False,
    ),
    "mathematica": BackendConfig(
        name="mathematica",
        command=["math"],
        description="Mathematica/Wolfram",
        prompt_regex=r"^In\[\d+\]:= ?$",
        supports_bracketed_paste=False,
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
        {"name": cfg.name, "description": cfg.description} for cfg in BACKENDS.values()
    ]
