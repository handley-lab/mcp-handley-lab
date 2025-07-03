"""Shared utilities for asynchronous command execution."""
import asyncio


async def run_command(
    cmd: list[str], input_data: bytes | None = None, timeout: int = 30
) -> tuple[bytes, bytes]:
    """Runs a command asynchronously, returning (stdout, stderr).

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
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(input=input_data), timeout=timeout
        )
        if process.returncode != 0:
            raise RuntimeError(
                f"Command failed with exit code {process.returncode}: {stderr.decode()}"
            )
        return stdout, stderr
    except FileNotFoundError:
        raise RuntimeError(f"Command not found: {cmd[0]}") from None
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise RuntimeError(f"Command timed out after {timeout} seconds") from None
