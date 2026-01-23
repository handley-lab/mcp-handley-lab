"""Sentinel protocol for detecting REPL command completion.

The sentinel protocol wraps user code with unique markers to reliably detect
when execution has completed and capture the output, even for commands that
produce no output or take a long time.
"""

import re
import uuid

from mcp_handley_lab.repl.backends import SentinelStyle


def generate_sentinel_id() -> str:
    """Generate a unique sentinel identifier."""
    return uuid.uuid4().hex[:12]


def wrap_code_with_sentinel(
    code: str,
    sentinel_id: str,
    style: SentinelStyle,
) -> str:
    """Wrap code with sentinel markers for completion detection.

    Args:
        code: The user code to execute.
        sentinel_id: Unique identifier for this execution.
        style: The sentinel style to use (SHELL or PYTHON).

    Returns:
        Wrapped code with start/end markers.
    """
    start_marker = f"__MCP_START_{sentinel_id}__"
    end_marker = f"__MCP_END_{sentinel_id}__"

    if style == SentinelStyle.SHELL:
        # For shell: echo markers and capture exit code
        return f'echo "{start_marker}"; {code}; echo "{end_marker}:$?"'

    elif style == SentinelStyle.PYTHON:
        # For Python: print markers
        # Use exec to handle multi-line code properly
        lines = code.strip().split("\n")
        if len(lines) == 1 and not any(
            lines[0].strip().startswith(kw)
            for kw in ("def ", "class ", "if ", "for ", "while ", "with ", "try:")
        ):
            # Single expression/statement - execute directly
            return f'print("{start_marker}")\n{code}\nprint("{end_marker}:0")'
        else:
            # Multi-line or compound statement
            return f'print("{start_marker}")\n{code}\nprint("{end_marker}:0")'

    raise ValueError(f"Unknown sentinel style: {style}")


def extract_output(
    raw_output: str,
    sentinel_id: str,
) -> tuple[str, int | None]:
    """Extract command output from sentinel-wrapped response.

    REPLs echo commands before executing them, so markers appear multiple times.
    This function uses a robust approach: find exit code from end marker, then
    filter out ALL lines related to sentinel infrastructure.

    Args:
        raw_output: Raw captured output from the REPL.
        sentinel_id: The sentinel identifier to look for.

    Returns:
        Tuple of (extracted_output, exit_code).
        exit_code is None if end sentinel wasn't found.
    """
    start_marker = f"__MCP_START_{sentinel_id}__"
    end_marker = f"__MCP_END_{sentinel_id}__"

    # First, find the exit code from the end marker (anywhere in output)
    exit_match = re.search(rf"{re.escape(end_marker)}:(\d+)", raw_output)
    exit_code = int(exit_match.group(1)) if exit_match else None

    if exit_code is None:
        # Command still running - return raw output for debugging
        return raw_output.strip(), None

    # Find the actual output region: after start marker output, before end marker output
    # Look for markers on their own line (actual output, not echoed command)
    start_pattern = rf"(?:^|\n){re.escape(start_marker)}\s*$"
    end_pattern = rf"(?:^|\n){re.escape(end_marker)}:\d+\s*$"

    start_match = re.search(start_pattern, raw_output, re.MULTILINE)
    end_match = re.search(end_pattern, raw_output, re.MULTILINE)

    if start_match and end_match and start_match.end() < end_match.start():
        # Extract content between the actual marker outputs
        content = raw_output[start_match.end():end_match.start()]
    else:
        # Fallback: take everything and filter aggressively
        content = raw_output

    # Aggressive cleanup: remove all sentinel-related lines and REPL noise
    lines = content.split("\n")
    cleaned_lines = []

    for line in lines:
        # Skip lines containing sentinel markers (echoed commands or actual output)
        if start_marker in line or end_marker in line:
            continue

        # Skip lines that are print/echo commands for sentinels
        if "print(" in line and "__MCP_" in line:
            continue
        if "echo " in line and "__MCP_" in line:
            continue

        # Skip empty prompt lines
        stripped = line.strip()
        if stripped in (">>>", "...", "$", "%", "In [", ""):
            continue

        # Remove leading prompts
        for prompt in (">>> ", "... ", "$ ", "% ", "In ["):
            if line.startswith(prompt):
                # Handle IPython prompts like "In [1]: "
                if prompt == "In [":
                    idx = line.find("]: ")
                    if idx != -1:
                        line = line[idx + 3:]
                else:
                    line = line[len(prompt):]
                break

        # Skip if line became empty after prompt removal
        if not line.strip():
            continue

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip(), exit_code


def check_completion(raw_output: str, sentinel_id: str) -> bool:
    """Check if the command execution has completed.

    Args:
        raw_output: Raw captured output from the REPL.
        sentinel_id: The sentinel identifier to look for.

    Returns:
        True if the end sentinel was found.
    """
    end_pattern = rf"__MCP_END_{sentinel_id}__:\d+"
    return bool(re.search(end_pattern, raw_output))
