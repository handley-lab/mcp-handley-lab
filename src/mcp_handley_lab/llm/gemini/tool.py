"""Gemini LLM tool for AI interactions via MCP."""

import base64
import io
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Literal, Optional

import numpy as np
from google import genai as google_genai
from google.genai.types import (
    Blob,
    EmbedContentConfig,
    FileData,
    GenerateContentConfig,
    GenerateImagesConfig,
    GoogleSearch,
    GoogleSearchRetrieval,
    Part,
    Tool,
)
from mcp.server.fastmcp import FastMCP
from PIL import Image
from pydantic import Field

from mcp_handley_lab.common.config import settings
from mcp_handley_lab.llm.common import (
    build_server_info,
    get_gemini_safe_mime_type,
    get_session_id,
    is_text_file,
    load_provider_models,
    resolve_image_data,
)
from mcp_handley_lab.llm.memory import memory_manager
from mcp_handley_lab.llm.model_loader import (
    get_structured_model_listing,
)
from mcp_handley_lab.llm.shared import process_image_generation, process_llm_request
from mcp_handley_lab.shared.models import (
    DocumentIndex,
    EmbeddingResult,
    ImageGenerationResult,
    IndexResult,
    LLMResult,
    ModelListing,
    SearchResult,
    ServerInfo,
    SimilarityResult,
)

mcp = FastMCP("Gemini Tool")

# Constants for configuration
GEMINI_INLINE_FILE_LIMIT_BYTES = 20 * 1024 * 1024  # 20MB
EMBEDDING_BATCH_SIZE = 100

# Type definitions
EmbeddingTaskType = Literal[
    "TASK_TYPE_UNSPECIFIED",
    "RETRIEVAL_QUERY",
    "RETRIEVAL_DOCUMENT",
    "SEMANTIC_SIMILARITY",
    "CLASSIFICATION",
    "CLUSTERING",
]

# Lazy initialization of Gemini client
_client: Optional[google_genai.Client] = None
_client_lock = threading.Lock()


def _get_client() -> google_genai.Client:
    """Get or create the global Gemini client with thread safety."""
    global _client
    with _client_lock:
        if _client is None:
            try:
                _client = google_genai.Client(api_key=settings.gemini_api_key)
            except Exception as e:
                raise RuntimeError(f"Failed to initialize Gemini client: {e}") from e
    return _client


# Generate session ID once at module load time
_SESSION_ID = f"_session_{os.getpid()}_{int(time.time())}"


# Load model configurations using shared loader
MODEL_CONFIGS, DEFAULT_MODEL, _get_model_config = load_provider_models("gemini")


def _calculate_cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calculate cosine similarity between two embedding vectors."""
    vec1_np = np.array(vec1)
    vec2_np = np.array(vec2)
    dot_product = np.dot(vec1_np, vec2_np)
    norm_product = np.linalg.norm(vec1_np) * np.linalg.norm(vec2_np)
    return dot_product / norm_product


def _get_session_id() -> LLMResult:
    """Get the persistent session ID for this MCP server process."""
    return get_session_id(mcp)


def _get_model_config(model: str) -> dict[str, int]:
    """Get token limits for a specific model."""
    return MODEL_CONFIGS.get(model, MODEL_CONFIGS[DEFAULT_MODEL])


def _resolve_files(
    files: list[str],
) -> tuple[list[Part], bool]:
    """Resolve file inputs to structured content parts for google-genai API.

    Uses inlineData for files <20MB and Files API for larger files.
    Returns tuple of (Part objects list, Files API used flag).
    """
    parts = []
    used_files_api = False
    for file_item in files:
        # Handle unified format: strings or {"path": "..."} dicts
        if isinstance(file_item, str):
            file_path = Path(file_item)
        elif isinstance(file_item, dict) and "path" in file_item:
            file_path = Path(file_item["path"])
        else:
            raise ValueError(f"Invalid file item format: {file_item}")
        file_size = file_path.stat().st_size

        if file_size > GEMINI_INLINE_FILE_LIMIT_BYTES:
            # Large file - use Files API
            used_files_api = True
            uploaded_file = _get_client().files.upload(
                file=str(file_path),
                mime_type=get_gemini_safe_mime_type(file_path),
            )
            parts.append(Part(fileData=FileData(fileUri=uploaded_file.uri)))
        else:
            # Small file - use inlineData with base64 encoding
            if is_text_file(file_path):
                # For text files, read directly as text
                content = file_path.read_text(encoding="utf-8")
                parts.append(Part(text=f"[File: {file_path.name}]\n{content}"))
            else:
                # For binary files, use inlineData
                file_content = file_path.read_bytes()
                encoded_content = base64.b64encode(file_content).decode()
                parts.append(
                    Part(
                        inlineData=Blob(
                            mimeType=get_gemini_safe_mime_type(file_path),
                            data=encoded_content,
                        )
                    )
                )

    return parts, used_files_api


def _resolve_images(
    images: list[str] | None = None,
) -> list[Image.Image]:
    """Resolve image inputs to PIL Image objects."""
    if images is None:
        images = []
    image_list = []

    # Handle images array
    for image_item in images:
        image_bytes = resolve_image_data(image_item)
        image_list.append(Image.open(io.BytesIO(image_bytes)))

    return image_list


def _gemini_generation_adapter(
    prompt: str,
    model: str,
    history: list[dict[str, str]],
    system_instruction: str,
    **kwargs,
) -> dict[str, Any]:
    """Gemini-specific text generation function for the shared processor."""
    # Extract Gemini-specific parameters
    temperature = kwargs.get("temperature", 1.0)
    grounding = kwargs.get("grounding", False)
    files = kwargs.get("files")
    max_output_tokens = kwargs.get("max_output_tokens")

    # Configure tools for grounding if requested
    tools = []
    if grounding:
        if model.startswith("gemini-1.5"):
            tools.append(Tool(google_search_retrieval=GoogleSearchRetrieval()))
        else:
            tools.append(Tool(google_search=GoogleSearch()))

    # Resolve file contents
    file_parts, used_files_api = _resolve_files(files)

    # Get model configuration and token limits
    model_config = _get_model_config(model)
    max_output = model_config["output_tokens"]
    output_tokens = (
        min(max_output_tokens, max_output) if max_output_tokens > 0 else max_output
    )

    # Prepare config
    config_params = {
        "temperature": temperature,
        "max_output_tokens": output_tokens,
    }
    if system_instruction:
        config_params["system_instruction"] = system_instruction
    if tools:
        config_params["tools"] = tools

    config = GenerateContentConfig(**config_params)

    # Convert history to Gemini format
    gemini_history = [
        {
            "role": "model" if msg["role"] == "assistant" else msg["role"],
            "parts": [{"text": msg["content"]}],
        }
        for msg in history
    ]

    # Generate content
    if gemini_history:
        # Continue existing conversation
        user_parts = [Part(text=prompt)] + file_parts
        contents = gemini_history + [
            {"role": "user", "parts": [part.to_json_dict() for part in user_parts]}
        ]
        response = _get_client().models.generate_content(
            model=model, contents=contents, config=config
        )
    else:
        # New conversation
        if file_parts:
            content_parts = [Part(text=prompt)] + file_parts
            response = _get_client().models.generate_content(
                model=model, contents=content_parts, config=config
            )
        else:
            response = _get_client().models.generate_content(
                model=model, contents=prompt, config=config
            )

    if not response.text:
        raise RuntimeError("No response text generated")

    # Extract grounding metadata - direct access, fail fast
    grounding_metadata = None
    response_dict = response.to_json_dict()
    if "candidates" in response_dict and response_dict["candidates"]:
        candidate = response_dict["candidates"][0]
        if "grounding_metadata" in candidate:
            metadata = candidate["grounding_metadata"]
            grounding_metadata = {
                "web_search_queries": metadata["web_search_queries"],
                "grounding_chunks": [
                    {"uri": chunk["web"]["uri"], "title": chunk["web"]["title"]}
                    for chunk in metadata["grounding_chunks"]
                    if "web" in chunk
                ],
                "grounding_supports": metadata["grounding_supports"],
                "search_entry_point": metadata["search_entry_point"],
            }

    # Extract additional response metadata - direct access
    finish_reason = ""
    avg_logprobs = 0.0
    if response.candidates and len(response.candidates) > 0:
        candidate = response.candidates[0]
        if candidate.finish_reason:
            finish_reason = str(candidate.finish_reason)
        if candidate.avg_logprobs is not None:
            avg_logprobs = float(candidate.avg_logprobs)

    # Extract generation time from server-timing header - fail fast on format changes
    # Files API responses don't include timing headers, only inline responses do
    generation_time_ms = 0
    if not used_files_api and response.sdk_http_response:
        http_dict = response.sdk_http_response.to_json_dict()
        headers = http_dict["headers"]
        server_timing = headers["server-timing"]
        if "dur=" in server_timing:
            # Extract duration from "gfet4t7; dur=11255" format. Fails loudly if format changes.
            dur_part = server_timing.split("dur=")[1].split(";")[0].split(",")[0]
            generation_time_ms = int(float(dur_part))

    return {
        "text": response.text,
        "input_tokens": response.usage_metadata.prompt_token_count,
        "output_tokens": response.usage_metadata.candidates_token_count,
        "grounding_metadata": grounding_metadata,
        "finish_reason": finish_reason,
        "avg_logprobs": avg_logprobs,
        "model_version": response.model_version,
        "generation_time_ms": generation_time_ms,
        "response_id": "",  # Gemini doesn't provide a response ID
    }


def _gemini_image_analysis_adapter(
    prompt: str,
    model: str,
    history: list[dict[str, str]],
    system_instruction: str,
    **kwargs,
) -> dict[str, Any]:
    """Gemini-specific image analysis function for the shared processor."""
    # Extract image analysis specific parameters
    images = kwargs.get("images", [])
    max_output_tokens = kwargs.get("max_output_tokens")

    # Load images
    image_list = _resolve_images(images)

    # Get model configuration
    model_config = _get_model_config(model)
    max_output = model_config["output_tokens"]
    output_tokens = (
        min(max_output_tokens, max_output) if max_output_tokens > 0 else max_output
    )

    # Prepare content with images
    content = [prompt] + image_list

    # Prepare the config
    config_params = {"max_output_tokens": output_tokens, "temperature": 1.0}
    if system_instruction:
        config_params["system_instruction"] = system_instruction

    config = GenerateContentConfig(**config_params)

    # Generate response - image analysis starts fresh conversation
    response = _get_client().models.generate_content(
        model=model, contents=content, config=config
    )

    if not response.text:
        raise RuntimeError("No response text generated")

    return {
        "text": response.text,
        "input_tokens": response.usage_metadata.prompt_token_count,
        "output_tokens": response.usage_metadata.candidates_token_count,
    }


@mcp.tool(
    description="Delegates a user query to external Google Gemini AI service on behalf of the human user. Returns Gemini's verbatim response to assist the user. Use `agent_name` for separate conversation thread with Gemini. For code reviews, use code2prompt first."
)
def ask(
    prompt: str = Field(
        ...,
        description="The user's question to delegate to external Gemini AI service.",
    ),
    output_file: str = Field(
        default="-",
        description="File path to save Gemini's response. Use '-' for standard output.",
    ),
    agent_name: str = Field(
        default="session",
        description="Separate conversation thread with Gemini AI service (distinct from your conversation with the user).",
    ),
    model: str = Field(
        default=DEFAULT_MODEL,
        description="The Gemini model to use for the request (e.g., 'gemini-1.5-pro-latest').",
    ),
    temperature: float = Field(
        default=1.0,
        description="Controls randomness in the response. Higher values (e.g., 1.0) are more creative, lower values are more deterministic.",
    ),
    grounding: bool = Field(
        default=False,
        description="If True, enables Google Search grounding to provide more factual, up-to-date responses.",
    ),
    files: list[str] = Field(
        default_factory=list,
        description="A list of file paths to provide as context to the model.",
    ),
    max_output_tokens: int = Field(
        default=0,
        description="The maximum number of tokens to generate in the response. 0 means use the model's default maximum.",
    ),
    system_prompt: str | None = Field(
        default=None,
        description="System instructions to send to external Gemini AI service. Remembered for this conversation thread.",
    ),
) -> LLMResult:
    """Ask Gemini a question with optional persistent memory."""
    return process_llm_request(
        prompt=prompt,
        output_file=output_file,
        agent_name=agent_name,
        model=model,
        provider="gemini",
        generation_func=_gemini_generation_adapter,
        mcp_instance=mcp,
        temperature=temperature,
        grounding=grounding,
        files=files,
        max_output_tokens=max_output_tokens,
        system_prompt=system_prompt,
    )


@mcp.tool(
    description="Delegates image analysis to external Gemini vision AI service on behalf of the user. Returns Gemini's verbatim visual analysis to assist the user."
)
def analyze_image(
    prompt: str = Field(
        ...,
        description="The user's question about the images to delegate to external Gemini vision AI service.",
    ),
    output_file: str = Field(
        default="-",
        description="File path to save Gemini's visual analysis. Use '-' for standard output.",
    ),
    files: list[str] = Field(
        default_factory=list,
        description="A list of image file paths or base64 encoded strings to be analyzed.",
    ),
    focus: str = Field(
        default="general",
        description="The area of focus for the analysis (e.g., 'ocr', 'objects'). Note: This is a placeholder parameter in the current implementation.",
    ),
    model: str = Field(
        default=DEFAULT_MODEL,
        description="The Gemini vision model to use (e.g., 'gemini-1.5-pro-latest').",
    ),
    agent_name: str = Field(
        default="session",
        description="Separate conversation thread with Gemini AI service (distinct from your conversation with the user).",
    ),
    max_output_tokens: int = Field(
        default=0,
        description="The maximum number of tokens to generate in the response. 0 means use the model's default maximum.",
    ),
    system_prompt: str | None = Field(
        default=None,
        description="System instructions to send to external Gemini AI service. Remembered for this conversation thread.",
    ),
) -> LLMResult:
    """Analyze images with Gemini vision model."""
    return process_llm_request(
        prompt=prompt,
        output_file=output_file,
        agent_name=agent_name,
        model=model,
        provider="gemini",
        generation_func=_gemini_image_analysis_adapter,
        mcp_instance=mcp,
        images=files,
        focus=focus,
        max_output_tokens=max_output_tokens,
        system_prompt=system_prompt,
    )


def _gemini_image_generation_adapter(prompt: str, model: str, **kwargs) -> dict:
    """Gemini-specific image generation function with comprehensive metadata extraction."""
    actual_model = model

    # Extract config parameters for metadata
    aspect_ratio = kwargs.get("aspect_ratio", "1:1")
    config = GenerateImagesConfig(number_of_images=1, aspect_ratio=aspect_ratio)

    response = _get_client().models.generate_images(
        model=actual_model,
        prompt=prompt,
        config=config,
    )

    if not response.generated_images or not response.generated_images[0].image:
        raise RuntimeError("Generated image has no data")

    # Extract response data
    generated_image = response.generated_images[0]
    image = generated_image.image

    # Get the prompt token count. No fallback. If this fails, the request fails.
    count_response = _get_client().models.count_tokens(
        model="gemini-1.5-flash-latest", contents=prompt
    )
    input_tokens = count_response.total_tokens

    # Extract safety attributes - direct access
    safety_attributes = {}
    if generated_image.safety_attributes:
        safety_attributes = {
            "categories": generated_image.safety_attributes.categories,
            "scores": generated_image.safety_attributes.scores,
            "content_type": generated_image.safety_attributes.content_type,
        }

    # Extract provider-specific metadata - direct access
    gemini_metadata = {
        "positive_prompt_safety_attributes": response.positive_prompt_safety_attributes,
        "actual_model_used": actual_model,
        "requested_model": model,
    }

    return {
        "image_bytes": image.image_bytes,
        "input_tokens": input_tokens,
        "enhanced_prompt": generated_image.enhanced_prompt or "",
        "original_prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "requested_format": "png",  # Gemini always returns PNG
        "mime_type": image.mime_type or "image/png",
        "cloud_uri": image.gcs_uri or "",
        "content_filter_reason": generated_image.rai_filtered_reason or "",
        "safety_attributes": safety_attributes,
        "gemini_metadata": gemini_metadata,
    }


@mcp.tool(
    description="Delegates image generation to external Google Imagen 3 AI service on behalf of the user. Returns the generated image file path to assist the user. Generated images are saved as PNG files."
)
def generate_image(
    prompt: str = Field(
        ...,
        description="The user's detailed description to send to external Imagen 3 AI service for image generation.",
    ),
    model: str = Field(
        default="imagen-3.0-generate-002",
        description="The Imagen model to use for image generation.",
    ),
    agent_name: str = Field(
        default="session",
        description="Separate conversation thread with image generation AI service (for prompt history tracking).",
    ),
) -> ImageGenerationResult:
    """Generate images with Google's Imagen 3 model."""
    return process_image_generation(
        prompt=prompt,
        agent_name=agent_name,
        model=model,
        provider="gemini",
        generation_func=_gemini_image_generation_adapter,
        mcp_instance=mcp,
    )


@mcp.tool(
    description="Generates embedding vectors for a given list of text strings using a specified model. Supports task-specific embeddings like 'SEMANTIC_SIMILARITY' or 'RETRIEVAL_DOCUMENT'."
)
def get_embeddings(
    contents: str | list[str] = Field(
        ...,
        description="The text string or list of text strings to be converted into embedding vectors.",
    ),
    model: str = Field(
        default="gemini-embedding-001", description="The embedding model to use."
    ),
    task_type: EmbeddingTaskType = Field(
        default="SEMANTIC_SIMILARITY",
        description="The intended use for the embedding. Affects how the embedding is generated. Options: 'RETRIEVAL_QUERY', 'RETRIEVAL_DOCUMENT', 'SEMANTIC_SIMILARITY', 'CLASSIFICATION', 'CLUSTERING'.",
    ),
    output_dimensionality: int = Field(
        default=0,
        description="The desired size of the output embedding vector. If 0, the model's default dimensionality is used.",
    ),
) -> list[EmbeddingResult]:
    """Generates embeddings for one or more text strings."""
    if isinstance(contents, str):
        contents = [contents]

    if not contents:
        raise ValueError("Contents list cannot be empty.")

    config_params = {"task_type": task_type.upper()}
    if output_dimensionality > 0:
        config_params["output_dimensionality"] = output_dimensionality

    config = EmbedContentConfig(**config_params)

    response = _get_client().models.embed_content(
        model=model, contents=contents, config=config
    )

    # Direct, elegant, and trusts the response structure. Let it fail.
    return [EmbeddingResult(embedding=e.values) for e in response.embeddings]


@mcp.tool(
    description="Calculates the semantic similarity score (cosine similarity) between two text strings. Returns a score between -1.0 and 1.0, where 1.0 is identical."
)
def calculate_similarity(
    text1: str = Field(..., description="The first text string for comparison."),
    text2: str = Field(..., description="The second text string for comparison."),
    model: str = Field(
        default="gemini-embedding-001",
        description="The embedding model to use for generating vectors for similarity calculation.",
    ),
) -> SimilarityResult:
    """Calculates the cosine similarity between two texts."""
    if not text1 or not text2:
        raise ValueError("Both text1 and text2 must be provided.")

    embeddings = get_embeddings(
        contents=[text1, text2],
        model=model,
        task_type="SEMANTIC_SIMILARITY",
        output_dimensionality=0,
    )

    if len(embeddings) != 2:
        raise RuntimeError("Failed to generate embeddings for both texts.")

    similarity = _calculate_cosine_similarity(
        embeddings[0].embedding, embeddings[1].embedding
    )

    return SimilarityResult(similarity=similarity)


@mcp.tool(
    description="Creates a searchable semantic index from a list of document file paths. It reads the files, generates embeddings for them, and saves the index as a JSON file."
)
def index_documents(
    document_paths: list[str] = Field(
        ...,
        description="A list of file paths to the text documents that need to be indexed.",
    ),
    output_index_path: str = Field(
        ..., description="The file path where the resulting JSON index will be saved."
    ),
    model: str = Field(
        default="gemini-embedding-001",
        description="The embedding model to use for creating the document index.",
    ),
) -> IndexResult:
    """Creates a semantic index from document files."""
    indexed_data = []
    batch_size = EMBEDDING_BATCH_SIZE  # Process documents in batches

    for i in range(0, len(document_paths), batch_size):
        batch_paths = document_paths[i : i + batch_size]
        batch_contents = []
        valid_paths = []

        for doc_path_str in batch_paths:
            doc_path = Path(doc_path_str)
            # If path is not a file, .read_text() will raise an error. This is desired.
            batch_contents.append(doc_path.read_text(encoding="utf-8"))
            valid_paths.append(doc_path_str)

        if not batch_contents:
            continue

        embedding_results = get_embeddings(
            contents=batch_contents,
            model=model,
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=0,
        )

        for path, emb_result in zip(valid_paths, embedding_results, strict=True):
            indexed_data.append(
                DocumentIndex(path=path, embedding=emb_result.embedding)
            )

    # Save the index to a file
    index_file = Path(output_index_path)
    index_file.parent.mkdir(parents=True, exist_ok=True)
    with open(index_file, "w") as f:
        # Pydantic's model_dump is used here to serialize our list of models
        json.dump([item.model_dump() for item in indexed_data], f, indent=2)

    return IndexResult(
        index_path=str(index_file),
        files_indexed=len(indexed_data),
        message=f"Successfully indexed {len(indexed_data)} files to {index_file}.",
    )


@mcp.tool(
    description="Performs a semantic search for a query against a pre-built document index file. Returns a ranked list of the most relevant documents based on similarity."
)
def search_documents(
    query: str = Field(..., description="The search query to find relevant documents."),
    index_path: str = Field(
        ...,
        description="The file path of the pre-computed JSON document index to search against.",
    ),
    top_k: int = Field(
        default=5, description="The number of top matching documents to return."
    ),
    model: str = Field(
        default="gemini-embedding-001",
        description="The embedding model to use for the query. Should match the model used to create the index.",
    ),
) -> list[SearchResult]:
    """Searches a document index for the most relevant documents to a query."""
    index_file = Path(index_path)
    # open() will raise FileNotFoundError. This is the correct behavior.
    with open(index_file) as f:
        indexed_data = json.load(f)

    if not indexed_data:
        return []

    # Get embedding for the query
    query_embedding_result = get_embeddings(
        contents=query,
        model=model,
        task_type="RETRIEVAL_QUERY",
        output_dimensionality=0,
    )
    query_embedding = query_embedding_result[0].embedding

    # Calculate similarities
    similarities = []
    for item in indexed_data:
        doc_embedding = item["embedding"]
        score = _calculate_cosine_similarity(query_embedding, doc_embedding)
        similarities.append({"path": item["path"], "score": score})

    # Sort by similarity and return top_k
    similarities.sort(key=lambda x: x["score"], reverse=True)

    results = [
        SearchResult(path=item["path"], similarity_score=item["score"])
        for item in similarities[:top_k]
    ]

    return results


@mcp.tool(
    description="Lists all available Gemini models with pricing, capabilities, and context windows. Helps compare models for cost, performance, and features to select the best model for specific tasks."
)
def list_models() -> ModelListing:
    """List available Gemini models with detailed information."""

    # Get models from API
    models_response = _get_client().models.list()
    api_model_names = {model.name.split("/")[-1] for model in models_response}

    # Use structured model listing
    return get_structured_model_listing("gemini", api_model_names)


@mcp.tool(
    description="Checks Gemini Tool server status and API connectivity. Returns version info, model availability, and a list of available functions."
)
def server_info() -> ServerInfo:
    """Get server status and Gemini configuration without making a network call."""

    # Get model names from the local YAML config instead of the API
    available_models = list(MODEL_CONFIGS.keys())

    # Add our new functions to the capabilities list
    info = build_server_info(
        provider_name="Gemini",
        available_models=available_models,
        memory_manager=memory_manager,
        vision_support=True,
        image_generation=True,
    )

    # Manually add embedding capabilities to the server info
    embedding_capabilities = [
        "get_embeddings - Generate embedding vectors for text.",
        "calculate_similarity - Compare two texts for semantic similarity.",
        "index_documents - Create a searchable index from files.",
        "search_documents - Search an index for a query.",
    ]
    info.capabilities.extend(embedding_capabilities)

    return info


@mcp.tool(description="Tests the connection to the Gemini API by listing models.")
def test_connection() -> str:
    """Tests the connection to the Gemini API."""
    try:
        models_response = _get_client().models.list()
        model_count = sum(
            1
            for model in models_response
            if "gemini" in model.name or "embedding" in model.name
        )
        return f"✅ Connection successful. Found {model_count} relevant models."
    except Exception as e:
        return f"❌ Connection failed: {e}"
