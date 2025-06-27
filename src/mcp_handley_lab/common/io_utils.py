"""Shared I/O utilities for file operations across tools."""
from pathlib import Path


def read_file_or_string(file_path: str | None, string_data: str | None) -> str | None:
    """Read content from file path or return string data directly."""
    if file_path:
        return Path(file_path).read_text()
    return string_data


def write_output_data(data: str, output_file: str) -> None:
    """Write data to file or stdout."""
    if output_file == '-':
        print(data)
    else:
        Path(output_file).write_text(data)


def get_input_data(file_path: str | None = None, string_data: str | None = None) -> str:
    """Get input data from file or string, with validation."""
    result = read_file_or_string(file_path, string_data)
    if result is None:
        raise ValueError("Must provide either file_path or string_data")
    return result


def ensure_file_exists(file_path: str | Path) -> Path:
    """Ensure file exists and return Path object."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return path
