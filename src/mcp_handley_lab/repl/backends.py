from typing import NamedTuple


class BackendConfig(NamedTuple):
    name: str
    command: list[str]
    description: str
    prompt_regex: str
    continuation_regex: str | None = None
    supports_bracketed_paste: bool = True
    echo_commands: bool = True


BACKENDS = {
    "bash": BackendConfig(
        "bash", ["bash", "--norc", "--noprofile"], "Bash shell", r"^.*\$ ?$"
    ),
    "python": BackendConfig(
        "python", ["python3", "-u"], "Python interpreter", r"^>>> ?$", r"^\.\.\."
    ),
    "ipython": BackendConfig(
        "ipython",
        ["ipython", "--simple-prompt", "--no-banner"],
        "IPython",
        r"^In \[\d+\]: ?$",
        r"^   \.\.\.:",
    ),
    "aichat": BackendConfig(
        "aichat",
        ["aichat", "--session", "mcp"],
        "aichat LLM",
        r"^> ?$",
        echo_commands=False,
    ),
    "ollama": BackendConfig(
        "ollama",
        ["ollama", "run", "llama3"],
        "Ollama LLM",
        r"^>>> ?$",
        echo_commands=False,
    ),
    "mathematica": BackendConfig(
        "mathematica",
        ["math"],
        "Mathematica",
        r"^In\[\d+\]:= ?$",
        supports_bracketed_paste=False,
    ),
}
