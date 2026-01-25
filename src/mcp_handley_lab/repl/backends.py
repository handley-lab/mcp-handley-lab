from typing import NamedTuple


class BackendConfig(NamedTuple):
    name: str
    command: list[str]
    description: str
    prompt_regex: str
    continuation_regex: str = ""
    supports_bracketed_paste: bool = True
    echo_commands: bool = True
    default_args: str = ""  # Used when no args provided


BACKENDS = {
    "bash": BackendConfig(
        "bash", ["bash", "--norc", "--noprofile"], "Bash shell", r"^.*\$ ?$"
    ),
    "zsh": BackendConfig("zsh", ["zsh", "--no-rcs"], "Zsh shell", r"^.*[%$#] ?$"),
    "python": BackendConfig(
        "python",
        ["python3", "-u"],
        "Python interpreter",
        r"^>>> ?$",
        r"^\.\.\.",
    ),
    "ipython": BackendConfig(
        "ipython",
        ["ipython"],
        "IPython",
        r"^In \[\d+\]: ?$",
        r"^   \.\.\.:",
        default_args="--matplotlib",
    ),
    "julia": BackendConfig("julia", ["julia"], "Julia", r"^julia> ?$"),
    "R": BackendConfig("R", ["R"], "R", r"^> ?$", r"^\+ ?$"),
    "clojure": BackendConfig(
        "clojure",
        ["clojure"],
        "Clojure",
        r"^[a-zA-Z0-9._-]+=> ?$",
        supports_bracketed_paste=False,
    ),
    "apl": BackendConfig(
        "apl",
        ["apl"],
        "GNU APL",
        r"      $",
        supports_bracketed_paste=False,
    ),
    "maple": BackendConfig(
        "maple",
        ["maple", "-c", "interface(errorcursor=false);"],
        "Maple",
        r"^> ?$",
    ),
    "ollama": BackendConfig(
        "ollama",
        ["ollama", "run", "llama3"],
        "Ollama LLM",
        r"^>>> ",
        supports_bracketed_paste=False,
        echo_commands=False,
    ),
    "mathematica": BackendConfig(
        "mathematica",
        ["math"],
        "Mathematica",
        r"^In\[\d+\]:= ?$",
        supports_bracketed_paste=False,
        default_args="-run $PrePrint=InputForm",
    ),
}
