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


class GroundingMetadata(BaseModel):
    """Grounding metadata for LLM responses."""

    web_search_queries: list[str] = []
    grounding_chunks: list[dict[str, str]] = []  # Contains uri and title
    grounding_supports: list[dict[str, Any]] = []  # Links text to sources
    retrieval_metadata: dict[str, Any] = {}  # Additional retrieval information
    search_entry_point: dict[str, Any] = {}  # Search interface HTML and queries


class LLMResult(BaseModel):
    """Standard LLM response structure."""

    content: str
    usage: UsageStats
    agent_name: str = ""
    grounding_metadata: GroundingMetadata | None = None
    finish_reason: str = ""
    avg_logprobs: float = 0.0
    model_version: str = ""
    generation_time_ms: int = 0
    response_id: str = ""
    # OpenAI-specific fields
    system_fingerprint: str = ""
    service_tier: str = ""
    completion_tokens_details: dict[str, Any] = {}
    prompt_tokens_details: dict[str, Any] = {}
    # Claude-specific fields
    stop_sequence: str = ""
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


class ImageGenerationResult(BaseModel):
    """Comprehensive image generation result structure with full metadata."""

    # Core result fields
    message: str
    file_path: str
    file_size_bytes: int
    usage: UsageStats
    agent_name: str = ""

    # Generation metadata
    generation_timestamp: int = 0  # Unix timestamp when image was generated
    enhanced_prompt: str = ""  # AI-enhanced version of original prompt
    original_prompt: str = ""  # Original user prompt

    # Request parameters (what was requested)
    requested_size: str = ""  # e.g., "1024x1024"
    requested_quality: str = ""  # e.g., "standard", "hd"
    requested_format: str = ""  # e.g., "png", "jpg"
    aspect_ratio: str = ""  # e.g., "1:1", "16:9"

    # Safety and content filtering
    safety_attributes: dict[str, Any] = {}  # Safety scores/flags from provider
    content_filter_reason: str = ""  # Reason if content was filtered

    # Provider-specific metadata
    openai_metadata: dict[str, Any] = {}  # OpenAI-specific fields
    gemini_metadata: dict[str, Any] = {}  # Gemini-specific fields

    # Technical details
    mime_type: str = ""  # e.g., "image/png"
    cloud_uri: str = ""  # Cloud storage URI if available
    original_url: str = ""  # Original download URL (OpenAI)


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


class ModelPricing(BaseModel):
    """Model pricing information."""

    type: Literal["per_token", "per_image", "per_second"]
    input_cost_per_1m: float = 0.0
    output_cost_per_1m: float = 0.0
    cost_per_image: float = 0.0
    cost_per_second: float = 0.0
    unit: str = "USD"


class ModelInfo(BaseModel):
    """Individual model information."""

    id: str
    name: str
    description: str
    available: bool
    context_window: str = ""
    pricing: ModelPricing
    tags: list[str] = []
    capabilities: list[str] = []
    best_for: list[str] = []


class ModelCategory(BaseModel):
    """Model category with associated models."""

    name: str
    models: list[ModelInfo]


class ModelListingSummary(BaseModel):
    """Summary information for model listing."""

    provider: str
    total_models: int
    total_categories: int
    default_model: str
    api_available_models: int = 0


class ModelListing(BaseModel):
    """Complete structured model listing."""

    summary: ModelListingSummary
    categories: list[ModelCategory]
    models: list[ModelInfo]
    usage_notes: list[str]


class MuttContact(BaseModel):
    """Mutt address book contact."""

    alias: str
    email: str
    name: str = ""


class MuttContactSearchResult(BaseModel):
    """Search result for mutt contacts."""

    query: str
    matches: list[MuttContact]
    total_found: int


class EmbeddingResult(BaseModel):
    """Result of an embedding request for a single piece of content."""

    embedding: list[float]


class DocumentIndex(BaseModel):
    """A single indexed document containing its path and embedding vector."""

    path: str
    embedding: list[float]


class IndexResult(BaseModel):
    """Result of an indexing operation."""

    index_path: str
    files_indexed: int
    message: str


class SearchResult(BaseModel):
    """A single result from a semantic search."""

    path: str
    similarity_score: float


class SimilarityResult(BaseModel):
    """Result of a similarity calculation between two texts."""

    similarity: float
