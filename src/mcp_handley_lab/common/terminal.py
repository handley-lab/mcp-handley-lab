"""Terminal utilities for launching interactive applications."""

import contextlib
import os
import re
import subprocess
import time
import uuid


def launch_interactive(
    command: str,
    window_title: str | None = None,
    prefer_tmux: bool = True,
    wait: bool = False,
) -> str | tuple[str, int]:
    """Launch an interactive command in a new terminal window.

    Automatically detects environment and chooses appropriate method:
    - If in tmux session: creates new tmux window
    - Otherwise: launches xterm window

    Args:
        command: The command to execute
        window_title: Optional title for the window
        prefer_tmux: Whether to prefer tmux over xterm when both available
        wait: Whether to wait for the command to complete before returning

    Returns:
        If wait=True: tuple of (status_message, exit_code)
        If wait=False: status message string describing what was launched

    Raises:
        RuntimeError: If neither tmux nor xterm is available
    """
    in_tmux = bool(os.environ.get("TMUX"))

    if in_tmux and prefer_tmux:
        if wait:
            unique_id = str(uuid.uuid4())[:8]
            window_name = f"task-{unique_id}"
            done_name = f"done-{unique_id}"

            sync_command = f"{command}; tmux rename-window '{done_name}'"
            tmux_cmd = ["tmux", "new-window", "-n", window_name, sync_command]

            try:
                current_window = subprocess.check_output(
                    ["tmux", "display-message", "-p", "#{window_index}"], text=True
                ).strip()

                subprocess.run(tmux_cmd, check=True)
                print(f"Waiting for user input from {window_title or 'tmux window'}...")

                while True:
                    output = subprocess.check_output(
                        ["tmux", "list-windows"], text=True
                    )
                    if re.search(rf"{done_name}", output):
                        break
                    if not re.search(rf"{window_name}", output):
                        break
                    time.sleep(0.1)

                if current_window:
                    with contextlib.suppress(subprocess.CalledProcessError):
                        subprocess.run(
                            ["tmux", "select-window", "-t", current_window], check=True
                        )

                return f"Completed in tmux window: {command}", 0
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Failed to run command in tmux: {e}") from e
        else:
            tmux_cmd = ["tmux", "new-window"]

            if window_title:
                tmux_cmd.extend(["-n", window_title])

            tmux_cmd.append(command)

            try:
                subprocess.run(tmux_cmd, check=True)
                return f"Launched in new tmux window: {command}"
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Failed to create tmux window: {e}") from e

    else:
        if wait:
            xterm_cmd = ["xterm"]

            if window_title:
                xterm_cmd.extend(["-title", window_title])

            xterm_cmd.extend(["-e", command])

            try:
                print(
                    f"Waiting for user input from {window_title or 'xterm window'}..."
                )
                result = subprocess.run(xterm_cmd)
                return f"Completed in xterm: {command}", result.returncode
            except FileNotFoundError as e:
                raise RuntimeError("xterm not available for interactive launch") from e
        else:
            xterm_cmd = ["xterm"]

            if window_title:
                xterm_cmd.extend(["-title", window_title])

            xterm_cmd.extend(["-e", command])

            try:
                subprocess.Popen(xterm_cmd)
                return f"Launched in xterm: {command}"
            except FileNotFoundError as e:
                raise RuntimeError(
                    "Neither tmux nor xterm available for interactive launch"
                ) from e


def check_interactive_support() -> dict:
    """Check what interactive terminal options are available.

    Returns:
        Dict with availability status of tmux and xterm
    """
    result = {
        "tmux_session": bool(os.environ.get("TMUX")),
        "tmux_available": False,
        "tmux_error": None,
        "xterm_available": False,
        "xterm_error": None,
    }

    try:
        subprocess.run(["tmux", "list-sessions"], capture_output=True, check=True)
        result["tmux_available"] = True
    except FileNotFoundError:
        pass
    except subprocess.CalledProcessError as e:
        result["tmux_error"] = str(e)

    try:
        subprocess.run(["which", "xterm"], capture_output=True, check=True)
        result["xterm_available"] = True
    except FileNotFoundError:
        pass
    except subprocess.CalledProcessError as e:
        result["xterm_error"] = str(e)

    return result
