"""Terminal utilities for launching interactive applications."""

import contextlib
import os
import subprocess
import uuid


def _tmux_server_running() -> bool:
    """True if a tmux server is reachable, regardless of whether $TMUX is set.

    The MCP server process does not inherit $TMUX from its parent, so keying
    off the environment variable misses an available tmux server. Probe the
    server directly instead.
    """
    return (
        subprocess.run(["tmux", "list-sessions"], capture_output=True).returncode == 0
    )


def launch_interactive(
    command: str,
    window_title: str | None = None,
    prefer_tmux: bool = True,
    wait: bool = False,
) -> str | tuple[str, int]:
    """Launch an interactive command in a new terminal window.

    Chooses the display method by capability, not by $TMUX:
    - If a tmux server is reachable: creates a new tmux window in it.
    - Otherwise: launches a ghostty window.

    Args:
        command: The command to execute
        window_title: Optional title for the window
        prefer_tmux: Whether to prefer tmux over ghostty when a server is reachable
        wait: Whether to wait for the command to complete before returning

    Returns:
        If wait=True: tuple of (status_message, exit_code)
        If wait=False: status message string describing what was launched
    """
    if prefer_tmux and _tmux_server_running():
        if wait:
            channel = f"wait-{str(uuid.uuid4())[:8]}"
            sync_command = f"{command}; tmux wait-for -S {channel}"

            current_window = subprocess.check_output(
                ["tmux", "display-message", "-p", "#{window_index}"], text=True
            ).strip()

            subprocess.run(["tmux", "new-window", sync_command], check=True)
            print(f"Waiting for user input from {window_title or 'tmux window'}...")
            subprocess.run(["tmux", "wait-for", channel], check=True)

            if current_window:
                with contextlib.suppress(subprocess.CalledProcessError):
                    subprocess.run(
                        ["tmux", "select-window", "-t", current_window], check=True
                    )

            return f"Completed in tmux window: {command}", 0

        tmux_cmd = ["tmux", "new-window"]
        if window_title:
            tmux_cmd.extend(["-n", window_title])
        tmux_cmd.append(command)

        subprocess.run(tmux_cmd, check=True)
        return f"Launched in new tmux window: {command}"

    # A shell command string needs a shell; ghostty's -e consumes the rest of
    # the args as the command, so it must come last. gtk-single-instance=false
    # forces a new blocking process so wait=True actually waits.
    ghostty_cmd = ["ghostty", "--gtk-single-instance=false"]
    if window_title:
        ghostty_cmd.append(f"--title={window_title}")
    ghostty_cmd.extend(["-e", "sh", "-c", command])

    if wait:
        print(f"Waiting for user input from {window_title or 'ghostty window'}...")
        result = subprocess.run(ghostty_cmd)
        return f"Completed in ghostty: {command}", result.returncode

    subprocess.Popen(ghostty_cmd)
    return f"Launched in ghostty: {command}"


def check_interactive_support() -> dict:
    """Check what interactive terminal options are available.

    Returns:
        Dict with availability status of tmux and ghostty
    """
    result = {
        "tmux_session": bool(os.environ.get("TMUX")),
        "tmux_available": False,
        "tmux_error": None,
        "ghostty_available": False,
        "ghostty_error": None,
    }

    try:
        subprocess.run(["tmux", "list-sessions"], capture_output=True, check=True)
        result["tmux_available"] = True
    except FileNotFoundError:
        pass
    except subprocess.CalledProcessError as e:
        result["tmux_error"] = str(e)

    try:
        subprocess.run(["which", "ghostty"], capture_output=True, check=True)
        result["ghostty_available"] = True
    except FileNotFoundError:
        pass
    except subprocess.CalledProcessError as e:
        result["ghostty_error"] = str(e)

    return result
