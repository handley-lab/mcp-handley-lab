from typing import Any, Literal

from pydantic import BaseModel


class ServerInfo(BaseModel):
    """Standardized server information across all tools."""

    name: str
    version: str
    status: str
    capabilities: list[str] = []
    dependencies: dict[str, str] = {}


class UsageStats(BaseModel):
    """LLM usage statistics."""

    input_tokens: int
    output_tokens: int
    cost: float
    model_used: str


class LLMResult(BaseModel):
    """Standard LLM response structure."""

    content: str
    usage: UsageStats
    agent_name: str = ""


class ImageGenerationResult(BaseModel):
    """Image generation result structure."""

    message: str
    file_path: str
    file_size_bytes: int
    usage: UsageStats
    agent_name: str = ""


class FileResult(BaseModel):
    """Standard file operation result."""

    message: str
    file_path: str
    file_size_bytes: int


class OperationResult(BaseModel):
    """Generic operation result."""

    status: Literal["success", "error", "warning"]
    message: str
    data: dict[str, Any] = {}
