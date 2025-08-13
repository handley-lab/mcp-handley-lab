from typing import Any, Literal

from pydantic import BaseModel, Field


class ServerInfo(BaseModel):
    """Standardized server information across all tools."""

    name: str = Field(..., description="The name of the MCP tool server.")
    version: str = Field(
        ..., description="The version of the tool or its primary dependency."
    )
    status: str = Field(
        ...,
        description="The operational status of the server (e.g., 'active', 'error').",
    )
    capabilities: list[str] = Field(
        default_factory=list,
        description="A list of functions or features the tool provides.",
    )
    dependencies: dict[str, str] = Field(
        default_factory=dict,
        description="A dictionary of dependencies and their versions or statuses.",
    )


class UsageStats(BaseModel):
    """LLM usage statistics."""

    input_tokens: int = Field(..., description="Number of tokens in the input prompt.")
    output_tokens: int = Field(
        ..., description="Number of tokens in the generated response."
    )
    cost: float = Field(..., description="Estimated cost of the API call in USD.")
    model_used: str = Field(
        ..., description="The specific model identifier used for generation."
    )


class GroundingMetadata(BaseModel):
    """Grounding metadata for LLM responses."""

    web_search_queries: list[str] = Field(
        default_factory=list, description="List of search queries used for grounding."
    )
    grounding_chunks: list[dict[str, str]] = Field(
        default_factory=list,
        description="Chunks of grounded content with URI and title information.",
    )
    grounding_supports: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Mapping between generated text and source citations.",
    )
    retrieval_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the retrieval process.",
    )
    search_entry_point: dict[str, Any] = Field(
        default_factory=dict, description="Search interface HTML and query information."
    )


class LLMResult(BaseModel):
    """Standard LLM response structure."""

    content: str = Field(..., description="The generated text content from the LLM.")
    usage: UsageStats = Field(
        ..., description="Token usage and cost information for the request."
    )
    agent_name: str = Field(
        default="", description="Name of the conversational agent or session."
    )
    grounding_metadata: GroundingMetadata | None = Field(
        default=None,
        description="Metadata about grounding sources used in the response.",
    )
    finish_reason: str = Field(
        default="",
        description="Reason why generation stopped (e.g., 'stop', 'length').",
    )
    avg_logprobs: float = Field(
        default=0.0, description="Average log probability of the generated tokens."
    )
    model_version: str = Field(
        default="", description="Specific version identifier of the model used."
    )
    generation_time_ms: int = Field(
        default=0, description="Time taken to generate the response in milliseconds."
    )
    response_id: str = Field(
        default="", description="Unique identifier for this specific response."
    )
    # OpenAI-specific fields
    system_fingerprint: str = Field(
        default="", description="OpenAI system fingerprint for the request."
    )
    service_tier: str = Field(
        default="", description="OpenAI service tier used for the request."
    )
    completion_tokens_details: dict[str, Any] = Field(
        default_factory=dict, description="Detailed token usage breakdown from OpenAI."
    )
    prompt_tokens_details: dict[str, Any] = Field(
        default_factory=dict,
        description="Detailed prompt token information from OpenAI.",
    )
    # Claude-specific fields
    stop_sequence: str = Field(
        default="", description="Stop sequence that terminated generation in Claude."
    )
    cache_creation_input_tokens: int = Field(
        default=0, description="Tokens used for cache creation in Claude."
    )
    cache_read_input_tokens: int = Field(
        default=0, description="Tokens read from cache in Claude."
    )


class ImageGenerationResult(BaseModel):
    """Comprehensive image generation result structure with full metadata."""

    # Core result fields
    message: str = Field(
        ..., description="Status message describing the image generation result."
    )
    file_path: str = Field(
        ..., description="Local file path where the generated image was saved."
    )
    file_size_bytes: int = Field(
        ..., description="Size of the generated image file in bytes."
    )
    usage: UsageStats = Field(
        ..., description="Cost and usage statistics for the image generation."
    )
    agent_name: str = Field(
        default="", description="Name of the agent or session that generated the image."
    )

    # Generation metadata
    generation_timestamp: int = Field(
        default=0, description="Unix timestamp when the image was generated."
    )
    enhanced_prompt: str = Field(
        default="", description="AI-enhanced version of the original prompt."
    )
    original_prompt: str = Field(
        default="", description="Original user prompt for the image generation."
    )

    # Request parameters (what was requested)
    requested_size: str = Field(
        default="", description="Requested image dimensions (e.g., '1024x1024')."
    )
    requested_quality: str = Field(
        default="", description="Requested image quality (e.g., 'standard', 'hd')."
    )
    requested_format: str = Field(
        default="", description="Requested image format (e.g., 'png', 'jpg')."
    )
    aspect_ratio: str = Field(
        default="", description="Image aspect ratio (e.g., '1:1', '16:9')."
    )

    # Safety and content filtering
    safety_attributes: dict[str, Any] = Field(
        default_factory=dict, description="Safety scores and flags from the provider."
    )
    content_filter_reason: str = Field(
        default="", description="Reason if content was filtered or rejected."
    )

    # Provider-specific metadata
    openai_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="OpenAI-specific metadata and response fields.",
    )
    gemini_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Gemini-specific metadata and response fields.",
    )

    # Technical details
    mime_type: str = Field(
        default="", description="MIME type of the generated image (e.g., 'image/png')."
    )
    cloud_uri: str = Field(
        default="", description="Cloud storage URI if the image is hosted remotely."
    )
    original_url: str = Field(
        default="", description="Original download URL from the provider."
    )


class FileResult(BaseModel):
    """Standard file operation result."""

    message: str = Field(
        ..., description="Status message describing the file operation result."
    )
    file_path: str = Field(
        ..., description="Path to the file that was created or modified."
    )
    file_size_bytes: int = Field(..., description="Size of the file in bytes.")


class OperationResult(BaseModel):
    """Generic operation result."""

    status: Literal["success", "error", "warning"] = Field(
        ..., description="The outcome status of the operation."
    )
    message: str = Field(
        ..., description="Human-readable description of the operation result."
    )
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional structured data related to the operation.",
    )


class ModelPricing(BaseModel):
    """Model pricing information."""

    type: Literal["per_token", "per_image", "per_second"] = Field(
        ..., description="The pricing model type used by this model."
    )
    input_cost_per_1m: float = Field(
        default=0.0,
        description="Cost per 1 million input tokens in the specified currency.",
    )
    output_cost_per_1m: float = Field(
        default=0.0,
        description="Cost per 1 million output tokens in the specified currency.",
    )
    cost_per_image: float = Field(
        default=0.0, description="Cost per generated image in the specified currency."
    )
    cost_per_second: float = Field(
        default=0.0,
        description="Cost per second of processing time in the specified currency.",
    )
    unit: str = Field(
        default="USD", description="Currency unit for all pricing information."
    )


class ModelInfo(BaseModel):
    """Individual model information."""

    id: str = Field(..., description="Unique identifier for the model.")
    name: str = Field(..., description="Human-readable name of the model.")
    description: str = Field(
        ...,
        description="Detailed description of the model's capabilities and use cases.",
    )
    available: bool = Field(
        ..., description="Whether the model is currently available for use."
    )
    context_window: str = Field(
        default="",
        description="Maximum context window size (e.g., '32K tokens', '2M tokens').",
    )
    pricing: ModelPricing = Field(
        ..., description="Pricing information for this model."
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Tags categorizing the model (e.g., 'multimodal', 'fast').",
    )
    capabilities: list[str] = Field(
        default_factory=list,
        description="List of specific capabilities this model supports.",
    )
    best_for: list[str] = Field(
        default_factory=list,
        description="List of use cases this model is optimized for.",
    )


class ModelCategory(BaseModel):
    """Model category with associated models."""

    name: str = Field(
        ...,
        description="Name of the model category (e.g., 'Text Generation', 'Vision').",
    )
    models: list[ModelInfo] = Field(..., description="List of models in this category.")


class ModelListingSummary(BaseModel):
    """Summary information for model listing."""

    provider: str = Field(
        ..., description="Name of the AI provider (e.g., 'OpenAI', 'Google')."
    )
    total_models: int = Field(
        ..., description="Total number of models available from this provider."
    )
    total_categories: int = Field(..., description="Number of model categories.")
    default_model: str = Field(
        ..., description="Default model identifier for this provider."
    )
    api_available_models: int = Field(
        default=0, description="Number of models available via API."
    )


class ModelListing(BaseModel):
    """Complete structured model listing."""

    summary: ModelListingSummary = Field(
        ..., description="Summary statistics for this model listing."
    )
    categories: list[ModelCategory] = Field(
        ..., description="Models organized by category."
    )
    models: list[ModelInfo] = Field(
        ..., description="Flat list of all available models."
    )
    usage_notes: list[str] = Field(
        ..., description="Important usage notes and limitations."
    )


class MuttContact(BaseModel):
    """Mutt address book contact."""

    alias: str = Field(
        ...,
        description="Short alias or nickname for the contact. Defaults to firstname-surname format in lowercase when adding contacts.",
    )
    email: str = Field(..., description="Email address of the contact.")
    name: str = Field(default="", description="Full name of the contact.")


class MuttContactSearchResult(BaseModel):
    """Search result for mutt contacts."""

    query: str = Field(..., description="The search query that was executed.")
    matches: list[MuttContact] = Field(
        ..., description="List of contacts matching the search query."
    )
    total_found: int = Field(..., description="Total number of contacts found.")


class EmbeddingResult(BaseModel):
    """Result of an embedding request for a single piece of content."""

    embedding: list[float] = Field(
        ..., description="Vector embedding as a list of floating-point numbers."
    )


class DocumentIndex(BaseModel):
    """A single indexed document containing its path and embedding vector."""

    path: str = Field(..., description="File path of the indexed document.")
    embedding: list[float] = Field(
        ..., description="Vector embedding for the document content."
    )


class IndexResult(BaseModel):
    """Result of an indexing operation."""

    index_path: str = Field(..., description="Path to the created index file.")
    files_indexed: int = Field(
        ..., description="Number of documents that were indexed."
    )
    message: str = Field(
        ..., description="Status message describing the indexing result."
    )


class SearchResult(BaseModel):
    """A single result from a semantic search."""

    path: str = Field(..., description="Path to the document that matched the search.")
    similarity_score: float = Field(
        ..., description="Similarity score between 0.0 and 1.0."
    )


class SimilarityResult(BaseModel):
    """Result of a similarity calculation between two texts."""

    similarity: float = Field(
        ..., description="Cosine similarity score between -1.0 and 1.0."
    )
