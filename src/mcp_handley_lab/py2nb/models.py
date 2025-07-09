"""Pydantic models for notebook conversion tool outputs."""
from pydantic import BaseModel


class ConversionResult(BaseModel):
    """Result of notebook conversion operation."""

    success: bool
    input_path: str
    output_path: str
    backup_path: str | None = None
    message: str


class ValidationResult(BaseModel):
    """Result of file validation operation."""

    valid: bool
    file_path: str
    message: str
    error_details: str | None = None


class RoundtripResult(BaseModel):
    """Result of round-trip conversion testing."""

    success: bool
    input_path: str
    differences_found: bool
    message: str
    diff_output: str | None = None
    temporary_files_cleaned: bool = True


class ExecutionResult(BaseModel):
    """Result of notebook execution operation."""

    success: bool
    notebook_path: str
    cells_executed: int
    cells_with_errors: int
    execution_time_seconds: float
    message: str
    error_details: str | None = None
    kernel_name: str | None = None


class ServerInfo(BaseModel):
    """Server status and dependency information."""

    status: str
    nbformat_version: str
    jupyter_info: str
    available_tools: list[str]
    comment_syntax: dict[str, str]
