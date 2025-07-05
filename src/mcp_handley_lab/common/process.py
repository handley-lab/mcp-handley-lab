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
        RuntimeError: If command fails, is not found, or times out
    """
    try:
        result = subprocess.run(
            cmd,
            input=input_data,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Command failed with exit code {result.returncode}: {result.stderr.decode()}"
            )
        return result.stdout, result.stderr
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"Command timed out after {timeout} seconds") from e
    except FileNotFoundError as e:
        raise RuntimeError(f"Command not found: {cmd[0]}") from e
