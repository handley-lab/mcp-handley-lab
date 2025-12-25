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
        subprocess.CalledProcessError: If command fails with non-zero exit code
        subprocess.TimeoutExpired: If command times out
        FileNotFoundError: If command is not found
    """
    result = subprocess.run(
        cmd,
        input=input_data,
        capture_output=True,
        timeout=timeout,
        check=True,
    )
    return result.stdout, result.stderr
