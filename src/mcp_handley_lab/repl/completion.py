"""Prompt-based completion detection with two-phase polling.

Detects command completion by watching for prompt reappearance combined with
output quiescence. Uses fast polling initially (for quick commands) then
switches to slower polling (for long-running commands).
"""

import re
import time
from dataclasses import dataclass


@dataclass
class CompletionResult:
    """Result of waiting for command completion."""

    completed: bool
    captured_output: str
    elapsed_seconds: float


class PromptDetector:
    """Detect command completion by prompt reappearance + quiescence."""

    def __init__(
        self,
        prompt_pattern: re.Pattern,
        fast_interval: float = 0.2,
        slow_interval: float = 3.0,
        fast_polls: int = 5,
        quiescence_ms: int = 150,
    ):
        self.prompt_pattern = prompt_pattern
        self.fast_interval = fast_interval
        self.slow_interval = slow_interval
        self.fast_polls = fast_polls
        self.quiescence_ms = quiescence_ms

    def count_prompts(self, text: str) -> int:
        """Count prompt occurrences in text."""
        return len(self.prompt_pattern.findall(text))

    def ends_with_prompt(self, text: str) -> bool:
        """Check if the last non-empty line is a prompt."""
        # Split without stripping - prompts may have trailing spaces
        lines = text.split("\n")
        # Find the last non-empty line (but don't strip its content)
        for line in reversed(lines):
            if line.strip():  # Found a non-empty line
                return bool(self.prompt_pattern.match(line))
        return False

    def wait_for_completion(
        self,
        capture_func,  # () -> str
        baseline_output: str,
        timeout: float,
        debug: bool = False,
    ) -> CompletionResult:
        """Poll until output ends with prompt and is stable.

        Uses two-phase polling:
        - Fast phase: 5 polls at 200ms intervals (catches commands < 1s)
        - Slow phase: 3s intervals (for long-running commands)

        Detection logic:
        - Output must end with a prompt (new prompt after command completion)
        - Output must have changed from baseline (command was executed)
        - Output must be stable for quiescence period (no more output coming)

        Args:
            capture_func: Function that returns current pane output.
            baseline_output: Output captured before sending command.
            timeout: Maximum seconds to wait.
            debug: If True, write debug info to /tmp/repl_debug.log

        Returns:
            CompletionResult with completion status and captured output.
        """
        start_time = time.time()
        poll_count = 0
        previous_output = baseline_output
        stable_since: float | None = None

        debug_file = None
        if debug:
            debug_file = open("/tmp/repl_debug.log", "w")
            debug_file.write(
                f"Baseline ({len(baseline_output)} chars): {repr(baseline_output[:100])}...\n"
            )
            debug_file.flush()

        while True:
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                if debug_file:
                    debug_file.write(f"TIMEOUT at {elapsed:.2f}s\n")
                    debug_file.close()
                return CompletionResult(
                    completed=False,
                    captured_output=previous_output,
                    elapsed_seconds=elapsed,
                )

            # Two-phase polling: fast then slow
            interval = (
                self.fast_interval
                if poll_count < self.fast_polls
                else self.slow_interval
            )
            time.sleep(interval)
            poll_count += 1

            current_output = capture_func()

            # Check for completion: output changed, ends with prompt, and stable
            output_changed = current_output != baseline_output
            ends_prompt = self.ends_with_prompt(current_output)
            same_as_prev = current_output == previous_output

            if debug_file:
                debug_file.write(
                    f"Poll {poll_count} ({elapsed:.2f}s): changed={output_changed}, ends_prompt={ends_prompt}, same_as_prev={same_as_prev}\n"
                )
                debug_file.flush()

            if output_changed and ends_prompt:
                # Quiescence check: output must be stable
                if same_as_prev:
                    if stable_since is None:
                        stable_since = time.time()
                        if debug_file:
                            debug_file.write("  -> Started quiescence timer\n")
                            debug_file.flush()
                    elif (time.time() - stable_since) * 1000 >= self.quiescence_ms:
                        if debug_file:
                            debug_file.write("  -> COMPLETED\n")
                            debug_file.close()
                        return CompletionResult(
                            completed=True,
                            captured_output=current_output,
                            elapsed_seconds=time.time() - start_time,
                        )
                else:
                    stable_since = None

            previous_output = current_output


def extract_output(
    baseline: str,
    captured: str,
    prompt_pattern: re.Pattern,
    sent_code: str,
    echo_commands: bool,
    continuation_pattern: re.Pattern | None = None,
) -> str:
    """Extract command output by comparing baseline and captured output.

    Strategy:
    1. Find where captured differs from baseline (the new content)
    2. Strip lines matching prompt or continuation patterns
    3. Strip echoed command lines
    4. Return the command output

    Args:
        baseline: Output captured before sending command.
        captured: Output captured after command completion.
        prompt_pattern: Compiled regex matching the REPL prompt.
        sent_code: The code that was sent (for echo filtering).
        echo_commands: Whether the REPL echoes sent commands.
        continuation_pattern: Optional regex for continuation prompts (e.g., "... ").

    Returns:
        Cleaned command output.
    """
    # Find where the new content starts
    # The baseline prompt line gets the command appended, so look for divergence
    baseline_lines = baseline.split("\n")
    captured_lines = captured.split("\n")

    # Find first line that differs
    start_idx = 0
    min_len = min(len(baseline_lines), len(captured_lines))
    for i in range(min_len):
        if baseline_lines[i] != captured_lines[i]:
            start_idx = i
            break
    else:
        # All compared lines match - new content is after baseline
        start_idx = len(baseline_lines)

    # Extract new content (from divergence point to end)
    new_lines = captured_lines[start_idx:]

    # Remove trailing empty lines first
    while new_lines and not new_lines[-1].strip():
        new_lines.pop()

    # Remove trailing prompt line(s)
    while new_lines and prompt_pattern.match(new_lines[-1]):
        new_lines.pop()

    # Remove any remaining trailing empty lines
    while new_lines and not new_lines[-1].strip():
        new_lines.pop()

    # Filter out continuation prompt lines (they're REPL chrome, not output)
    if continuation_pattern:
        new_lines = [line for line in new_lines if not continuation_pattern.match(line)]

    # Remove leading command echo if present
    if echo_commands and new_lines and sent_code.strip():
        first_code_line = sent_code.strip().split("\n")[0].strip()
        # The first new line might be "prompt + command" or just the command
        if new_lines:
            first_line = new_lines[0]
            # Check if line contains the command (prompt prefix + command)
            if first_code_line in first_line:
                new_lines.pop(0)

    # Also filter out any remaining echoed code lines
    if echo_commands and sent_code.strip():
        code_lines = {
            line.strip() for line in sent_code.strip().split("\n") if line.strip()
        }
        filtered = []
        for line in new_lines:
            stripped = line.strip()
            if stripped in code_lines:
                code_lines.discard(stripped)  # Only skip once
            else:
                filtered.append(line)
        new_lines = filtered

    return "\n".join(new_lines).strip()
