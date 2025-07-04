"""Terminal utilities for launching interactive applications."""

import os
import re
import subprocess
import time
import uuid
from typing import Optional


def launch_interactive(
    command: str,
    window_title: Optional[str] = None,
    prefer_tmux: bool = True,
    wait: bool = False,
) -> str:
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
        Status message describing what was launched

    Raises:
        RuntimeError: If neither tmux nor xterm is available
    """
    in_tmux = bool(os.environ.get("TMUX"))

    if in_tmux and prefer_tmux:
        # Launch in new tmux window
        if wait:
            # Use tmux window name as signal (clean UX)
            unique_id = str(uuid.uuid4())[:8]
            window_name = f"task-{unique_id}"
            done_name = f"done-{unique_id}"

            # Command with window rename after completion
            sync_command = f"{command}; tmux rename-window '{done_name}'"
            tmux_cmd = ["tmux", "new-window", "-n", window_name, sync_command]

            try:
                # Get current window index RIGHT BEFORE launching (not at function start)
                current_window = subprocess.check_output(
                    ["tmux", "display-message", "-p", "#{window_index}"], text=True
                ).strip()

                subprocess.run(tmux_cmd, check=True)
                print(f"Waiting for user input from {window_title or 'tmux window'}...")

                # Poll tmux list-windows for the renamed window (no timeout)
                while True:
                    output = subprocess.check_output(
                        ["tmux", "list-windows"], text=True
                    )
                    if re.search(rf"{done_name}", output):
                        break
                    # Also check if the window still exists
                    if not re.search(rf"{window_name}", output):
                        # Window was closed/renamed by user - consider it done
                        break
                    time.sleep(0.1)

                # Return to the window we were in when mutt was launched
                if current_window:
                    try:
                        subprocess.run(
                            ["tmux", "select-window", "-t", current_window], check=True
                        )
                    except subprocess.CalledProcessError:
                        pass  # Original window might not exist anymore

                return f"Completed in tmux window: {command}"
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Failed to run command in tmux: {e}") from e
        else:
            # Async execution (original behavior)
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
        # Fallback to xterm
        if wait:
            # For xterm, we can wait on the xterm process itself
            xterm_cmd = ["xterm"]

            if window_title:
                xterm_cmd.extend(["-title", window_title])

            xterm_cmd.extend(["-e", command])

            try:
                print(
                    f"Waiting for user input from {window_title or 'xterm window'}..."
                )
                # xterm process will exit when the command inside exits
                subprocess.run(xterm_cmd, check=True)
                return f"Completed in xterm: {command}"
            except FileNotFoundError as e:
                raise RuntimeError("xterm not available for interactive launch") from e
        else:
            # Async execution (original behavior)
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

    # Check tmux availability
    try:
        subprocess.run(["tmux", "list-sessions"], capture_output=True, check=True)
        result["tmux_available"] = True
    except FileNotFoundError:
        pass  # tmux not installed, expected
    except subprocess.CalledProcessError as e:
        result["tmux_error"] = str(e)

    # Check xterm availability
    try:
        subprocess.run(["which", "xterm"], capture_output=True, check=True)
        result["xterm_available"] = True
    except FileNotFoundError:
        pass  # xterm not installed, expected
    except subprocess.CalledProcessError as e:
        result["xterm_error"] = str(e)

    return result


def get_recommended_launcher() -> str:
    """Get the recommended interactive launcher for current environment.

    Returns:
        'tmux' or 'xterm' based on current environment
    """
    support = check_interactive_support()

    if support["tmux_session"] and support["tmux_available"]:
        return "tmux"
    elif support["xterm_available"]:
        return "xterm"
    else:
        raise RuntimeError("No interactive terminal launcher available")
