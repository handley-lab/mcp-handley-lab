"""Pydantic models for notebook conversion tool outputs."""

from pydantic import BaseModel, Field


class ConversionResult(BaseModel):
    """Result of notebook conversion operation."""

    success: bool = Field(..., description="Indicates if the conversion was successful.")
    input_path: str = Field(..., description="The absolute path of the source file.")
    output_path: str = Field(..., description="The absolute path of the newly created destination file.")
    backup_path: str | None = Field(default=None, description="The path to the backup of the original file, if one was created.")
    message: str = Field(..., description="A human-readable summary of the conversion result.")


class ValidationResult(BaseModel):
    """Result of file validation operation."""

    valid: bool = Field(..., description="Indicates if the file passed validation.")
    file_path: str = Field(..., description="The path to the file that was validated.")
    message: str = Field(..., description="A summary of the validation result.")
    error_details: str | None = Field(default=None, description="Detailed error information if validation failed.")


class RoundtripResult(BaseModel):
    """Result of round-trip conversion testing."""

    success: bool = Field(..., description="Indicates if the round-trip conversion completed successfully.")
    input_path: str = Field(..., description="The path to the original file used for round-trip testing.")
    differences_found: bool = Field(..., description="Whether any differences were detected between original and round-trip result.")
    message: str = Field(..., description="A summary of the round-trip test result.")
    diff_output: str | None = Field(default=None, description="Detailed diff output if differences were found.")
    temporary_files_cleaned: bool = Field(default=True, description="Whether temporary files created during testing were cleaned up.")


class ExecutionResult(BaseModel):
    """Result of notebook execution operation."""

    success: bool = Field(..., description="Indicates if the notebook execution completed successfully.")
    notebook_path: str = Field(..., description="The path to the notebook that was executed.")
    cells_executed: int = Field(..., description="The total number of cells that were executed.")
    cells_with_errors: int = Field(..., description="The number of cells that encountered errors during execution.")
    execution_time_seconds: float = Field(..., description="The total time taken to execute the notebook in seconds.")
    message: str = Field(..., description="A summary of the execution result.")
    error_details: str | None = Field(default=None, description="Detailed error information if execution failed.")
    kernel_name: str | None = Field(default=None, description="The name of the Jupyter kernel used for execution.")


