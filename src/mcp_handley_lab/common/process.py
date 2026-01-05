"""Shared utilities for command execution."""

import subprocess


def run_command(
    cmd: list[str], input_data: bytes | None = None, timeout: int = 30
) -> tuple[bytes, bytes]:
    """Runs a command synchronously, returning (stdout, stderr).

    Args:
        cmd: Command and arguments as a list
        input_data: Optional stdin data to send to the process
        timeout: Timeout in seconds (default: 30)

    Returns:
        Tuple of (stdout, stderr) as bytes

    Raises:
        RuntimeError: If command fails (includes stderr in message)
        subprocess.TimeoutExpired: If command times out
        FileNotFoundError: If command is not found
    """
    try:
        result = subprocess.run(
            cmd,
            input=input_data,
            capture_output=True,
            timeout=timeout,
            check=True,
        )
        return result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        stderr_msg = e.stderr.decode(errors="replace").strip() if e.stderr else ""
        cmd_str = " ".join(cmd)
        raise RuntimeError(
            f"Command failed (exit {e.returncode}): {cmd_str}\n{stderr_msg}"
        ) from e
