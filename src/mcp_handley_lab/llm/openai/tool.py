"""OpenAI LLM tool for AI interactions via MCP."""

import json
from pathlib import Path
from typing import Any

import httpx
import numpy as np
from mcp.server.fastmcp import FastMCP
from openai import OpenAI
from pydantic import Field

from mcp_handley_lab.common.config import settings
from mcp_handley_lab.llm.common import (
    build_server_info,
    load_provider_models,
    resolve_files_for_llm,
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

mcp = FastMCP("OpenAI Tool")

# Constants for embedding configuration
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_BATCH_SIZE = 100

# Configure OpenAI client
client = OpenAI(api_key=settings.openai_api_key)

# Load model configurations using shared loader
MODEL_CONFIGS, DEFAULT_MODEL, _get_model_config = load_provider_models("openai")


def _openai_generation_adapter(
    prompt: str,
    model: str,
    history: list[dict[str, str]],
    system_instruction: str,
    **kwargs,
) -> dict[str, Any]:
    """OpenAI-specific text generation function for the shared processor."""
    # Extract OpenAI-specific parameters
    temperature = kwargs.get("temperature", 1.0)
    files = kwargs.get("files")
    max_output_tokens = kwargs.get("max_output_tokens")
    enable_logprobs = kwargs["enable_logprobs"]
    top_logprobs = kwargs["top_logprobs"]

    # Build messages
    messages = []

    # Add system instruction if provided
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})

    # Add history (already in OpenAI format)
    messages.extend(history)

    # Resolve files
    inline_content = resolve_files_for_llm(files)

    # Add user message with any inline content
    user_content = prompt
    if inline_content:
        user_content += "\n\n" + "\n\n".join(inline_content)
    messages.append({"role": "user", "content": user_content})

    # Get model configuration
    model_config = _get_model_config(model)
    param_name = model_config["param"]
    default_tokens = model_config["output_tokens"]

    # Build request parameters
    request_params = {
        "model": model,
        "messages": messages,
    }

    # Add logprobs if requested
    if enable_logprobs:
        request_params["logprobs"] = True
        if top_logprobs > 0:
            request_params["top_logprobs"] = top_logprobs

    request_params["temperature"] = temperature

    # Add max tokens with correct parameter name
    if max_output_tokens > 0:
        request_params[param_name] = max_output_tokens
    else:
        request_params[param_name] = default_tokens

    # Make API call
    response = client.chat.completions.create(**request_params)

    if not response.choices or not response.choices[0].message.content:
        raise RuntimeError("No response generated")

    # Extract additional OpenAI metadata
    choice = response.choices[0]
    finish_reason = choice.finish_reason

    # Extract logprobs for confidence assessment
    avg_logprobs = 0.0
    if choice.logprobs and choice.logprobs.content:
        logprobs = [token.logprob for token in choice.logprobs.content]
        avg_logprobs = sum(logprobs) / len(logprobs)

    # Extract token details
    completion_tokens_details = {}
    if response.usage.completion_tokens_details:
        details = response.usage.completion_tokens_details
        completion_tokens_details = {
            "reasoning_tokens": details.reasoning_tokens,
            "accepted_prediction_tokens": details.accepted_prediction_tokens,
            "rejected_prediction_tokens": details.rejected_prediction_tokens,
            "audio_tokens": details.audio_tokens,
        }

    prompt_tokens_details = {}
    if response.usage.prompt_tokens_details:
        details = response.usage.prompt_tokens_details
        prompt_tokens_details = {
            "cached_tokens": details.cached_tokens,
            "audio_tokens": details.audio_tokens,
        }

    return {
        "text": response.choices[0].message.content,
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
        "finish_reason": finish_reason,
        "avg_logprobs": avg_logprobs,
        "model_version": response.model,
        "response_id": response.id,
        "system_fingerprint": response.system_fingerprint or "",
        "service_tier": response.service_tier or "",
        "completion_tokens_details": completion_tokens_details,
        "prompt_tokens_details": prompt_tokens_details,
    }


def _openai_image_analysis_adapter(
    prompt: str,
    model: str,
    history: list[dict[str, str]],
    system_instruction: str,
    **kwargs,
) -> dict[str, Any]:
    """OpenAI-specific image analysis function for the shared processor."""
    # Extract image analysis specific parameters
    images = kwargs.get("images", [])
    focus = kwargs.get("focus", "general")
    max_output_tokens = kwargs.get("max_output_tokens")

    # Use standardized image processing
    from mcp_handley_lab.llm.common import resolve_images_for_multimodal_prompt

    # Enhance prompt based on focus
    if focus != "general":
        prompt = f"Focus on {focus} aspects. {prompt}"

    prompt_text, image_blocks = resolve_images_for_multimodal_prompt(prompt, images)

    # Build message content with images in OpenAI format
    content = [{"type": "text", "text": prompt_text}]
    for image_block in image_blocks:
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{image_block['mime_type']};base64,{image_block['data']}"
                },
            }
        )

    # Build messages
    messages = []

    # Add system instruction if provided
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})

    # Add history (already in OpenAI format)
    messages.extend(history)

    # Add current message with images
    messages.append({"role": "user", "content": content})

    # Get model configuration
    model_config = _get_model_config(model)
    param_name = model_config["param"]
    default_tokens = model_config["output_tokens"]

    # Build request parameters
    request_params = {
        "model": model,
        "messages": messages,
    }

    # Only add temperature for models that support it (reasoning models don't)
    if not model.startswith(("o1", "o3", "o4")):
        request_params["temperature"] = 1.0

    # Add max tokens with correct parameter name
    if max_output_tokens > 0:
        request_params[param_name] = max_output_tokens
    else:
        request_params[param_name] = default_tokens

    # Make API call
    response = client.chat.completions.create(**request_params)

    if not response.choices or not response.choices[0].message.content:
        raise RuntimeError("No response generated")

    return {
        "text": response.choices[0].message.content,
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
        "finish_reason": response.choices[0].finish_reason,
        "avg_logprobs": 0.0,  # Image analysis doesn't use logprobs
        "model_version": response.model,
        "response_id": response.id,
        "system_fingerprint": response.system_fingerprint or "",
        "service_tier": response.service_tier or "",
        "completion_tokens_details": {},  # Not available for vision models
        "prompt_tokens_details": {},  # Not available for vision models
    }


@mcp.tool(
    description="Sends a prompt to an OpenAI model for conversational response. Use `agent_name` for persistent memory and `files` for context. For code reviews, use code2prompt first."
)
def ask(
    prompt: str = Field(
        ..., description="The main question or instruction for the AI model."
    ),
    output_file: str = Field(
        default="-",
        description="File path to save the output. Use '-' for standard output.",
    ),
    agent_name: str = Field(
        default="session",
        description="Enables persistent conversation memory.",
    ),
    model: str = Field(
        default=DEFAULT_MODEL,
        description="The OpenAI GPT model to use for the request (e.g., 'gpt-4o').",
    ),
    temperature: float = Field(
        default=1.0,
        description="Controls response randomness (0.0-2.0). Higher is more creative.",
    ),
    max_output_tokens: int = Field(
        default=0,
        description="Max response tokens. 0 for model's default max.",
    ),
    files: list[str] = Field(
        default_factory=list,
        description="List of file paths to include as context.",
    ),
    enable_logprobs: bool = Field(
        default=False,
        description="Return log probabilities for output tokens for confidence scoring.",
    ),
    top_logprobs: int = Field(
        default=0,
        description="Number of top-N logprobs to return per token (0-5). Requires enable_logprobs.",
    ),
    system_prompt: str | None = Field(
        default=None,
        description="Persistent system instruction for the agent's behavior.",
    ),
) -> LLMResult:
    """Ask OpenAI a question with optional persistent memory."""
    return process_llm_request(
        prompt=prompt,
        output_file=output_file,
        agent_name=agent_name,
        model=model,
        provider="openai",
        generation_func=_openai_generation_adapter,
        mcp_instance=mcp,
        temperature=temperature,
        files=files,
        max_output_tokens=max_output_tokens,
        enable_logprobs=enable_logprobs,
        top_logprobs=top_logprobs,
        system_prompt=system_prompt,
    )


@mcp.tool(
    description="Analyzes images with an OpenAI vision model. Supports persistent memory."
)
def analyze_image(
    prompt: str = Field(
        ..., description="The question or instruction related to the images."
    ),
    output_file: str = Field(
        default="-",
        description="File path to save the analysis output. Use '-' for standard output.",
    ),
    files: list[str] = Field(
        default_factory=list,
        description="A list of image file paths or base64 encoded strings to be analyzed.",
    ),
    focus: str = Field(
        default="general",
        description="The area of focus for the analysis (e.g., 'ocr', 'objects'). This enhances the prompt to guide the model.",
    ),
    model: str = Field(
        default="gpt-4o", description="The OpenAI vision model to use (e.g., 'gpt-4o')."
    ),
    agent_name: str = Field(
        default="session",
        description="Enables persistent conversation memory.",
    ),
    max_output_tokens: int = Field(
        default=0,
        description="The maximum number of tokens to generate in the response. 0 means use the model's default maximum.",
    ),
    system_prompt: str | None = Field(
        default=None,
        description="Persistent system instruction for the agent's behavior.",
    ),
) -> LLMResult:
    """Analyze images with OpenAI vision model."""
    return process_llm_request(
        prompt=prompt,
        output_file=output_file,
        agent_name=agent_name,
        model=model,
        provider="openai",
        generation_func=_openai_image_analysis_adapter,
        mcp_instance=mcp,
        images=files,
        focus=focus,
        max_output_tokens=max_output_tokens,
        system_prompt=system_prompt,
    )


def _openai_image_generation_adapter(prompt: str, model: str, **kwargs) -> dict:
    """OpenAI-specific image generation function with comprehensive metadata extraction."""
    # Extract parameters for metadata
    size = kwargs.get("size", "1024x1024")
    quality = kwargs.get("quality", "standard")

    params = {"model": model, "prompt": prompt, "size": size, "n": 1}
    if model == "dall-e-3":
        params["quality"] = quality

    response = client.images.generate(**params)
    image = response.data[0]

    # Download the image
    with httpx.Client() as http_client:
        image_response = http_client.get(image.url)
        image_response.raise_for_status()
        image_bytes = image_response.content

    # Extract comprehensive metadata
    openai_metadata = {
        "background": getattr(response, "background", None),
        "output_format": getattr(response, "output_format", None),
        "usage": getattr(response, "usage", None),
    }

    return {
        "image_bytes": image_bytes,
        "generation_timestamp": response.created,
        "enhanced_prompt": image.revised_prompt or "",
        "original_prompt": prompt,
        "requested_size": size,
        "requested_quality": quality,
        "requested_format": "png",  # OpenAI always returns PNG
        "mime_type": "image/png",
        "original_url": image.url,
        "openai_metadata": openai_metadata,
    }


@mcp.tool(
    description="Generates images using DALL-E models from text prompts. Supports quality and size options."
)
def generate_image(
    prompt: str = Field(
        ..., description="A detailed, creative description of the image to generate."
    ),
    model: str = Field(
        default="dall-e-3",
        description="The DALL-E model to use for image generation (e.g., 'dall-e-3', 'dall-e-2').",
    ),
    quality: str = Field(
        default="standard",
        description="The quality of the generated image. 'hd' for higher detail, 'standard' for faster generation. Only applies to dall-e-3.",
    ),
    size: str = Field(
        default="1024x1024",
        description="The dimensions of the image. Options vary by model: '1024x1024', '1792x1024', '1024x1792' for DALL-E 3.",
    ),
    agent_name: str = Field(
        default="session",
        description="Identifier for the conversation memory to store prompt history.",
    ),
) -> ImageGenerationResult:
    """Generate images with DALL-E."""
    return process_image_generation(
        prompt=prompt,
        agent_name=agent_name,
        model=model,
        provider="openai",
        generation_func=_openai_image_generation_adapter,
        mcp_instance=mcp,
        quality=quality,
        size=size,
    )


def _calculate_cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calculate cosine similarity between two embedding vectors."""
    vec1_np = np.array(vec1)
    vec2_np = np.array(vec2)
    dot_product = np.dot(vec1_np, vec2_np)
    norm_product = np.linalg.norm(vec1_np) * np.linalg.norm(vec2_np)
    return dot_product / norm_product


@mcp.tool(
    description="Generates embedding vectors for text. Supports v3 model 'dimensions' param."
)
def get_embeddings(
    contents: str | list[str] = Field(
        ...,
        description="A single text string or a list of text strings to be converted into embedding vectors.",
    ),
    model: str = Field(
        default=DEFAULT_EMBEDDING_MODEL,
        description="The embedding model to use (e.g., 'text-embedding-3-small').",
    ),
    dimensions: int = Field(
        default=0,
        description="The desired size of the output embedding vector. If 0, the model's default is used. Only for v3 embedding models.",
    ),
) -> list[EmbeddingResult]:
    """Generates embeddings for one or more text strings."""
    if isinstance(contents, str):
        contents = [contents]

    if not contents:
        raise ValueError("Contents list cannot be empty.")

    params = {"model": model, "input": contents}

    # Only add dimensions parameter for v3 models
    if dimensions > 0 and "3" in model:
        params["dimensions"] = dimensions

    # Direct, fail-fast API call
    response = client.embeddings.create(**params)

    # Direct access - trust the response structure
    return [EmbeddingResult(embedding=item.embedding) for item in response.data]


@mcp.tool(
    description="Calculates cosine similarity between two texts. Returns score from -1.0 to 1.0."
)
def calculate_similarity(
    text1: str = Field(..., description="The first text string for comparison."),
    text2: str = Field(..., description="The second text string for comparison."),
    model: str = Field(
        default=DEFAULT_EMBEDDING_MODEL,
        description="The embedding model to use for generating vectors for similarity calculation.",
    ),
) -> SimilarityResult:
    """Calculates the cosine similarity between two texts."""
    if not text1 or not text2:
        raise ValueError("Both text1 and text2 must be provided.")

    embeddings = get_embeddings(contents=[text1, text2], model=model, dimensions=0)

    if len(embeddings) != 2:
        raise RuntimeError("Failed to generate embeddings for both texts.")

    similarity = _calculate_cosine_similarity(
        embeddings[0].embedding, embeddings[1].embedding
    )

    return SimilarityResult(similarity=similarity)


@mcp.tool(
    description="Creates a semantic index from document files by generating and saving embeddings."
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
        default=DEFAULT_EMBEDDING_MODEL,
        description="The embedding model to use for creating the document index.",
    ),
) -> IndexResult:
    """Creates a semantic index from document files."""
    indexed_data = []
    batch_size = EMBEDDING_BATCH_SIZE

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
            contents=batch_contents, model=model, dimensions=0
        )

        for path, emb_result in zip(valid_paths, embedding_results, strict=True):
            indexed_data.append(
                DocumentIndex(path=path, embedding=emb_result.embedding)
            )

    # Save the index to a file
    index_file = Path(output_index_path)
    index_file.parent.mkdir(parents=True, exist_ok=True)
    with open(index_file, "w") as f:
        json.dump([item.model_dump() for item in indexed_data], f, indent=2)

    return IndexResult(
        index_path=str(index_file),
        files_indexed=len(indexed_data),
        message=f"Successfully indexed {len(indexed_data)} files to {index_file}.",
    )


@mcp.tool(
    description="Searches a document index with a query. Returns a ranked list of docs by similarity."
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
        default=DEFAULT_EMBEDDING_MODEL,
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
    query_embedding_result = get_embeddings(contents=query, model=model, dimensions=0)
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
    description="Retrieves a catalog of available OpenAI models with their capabilities, pricing, and context windows. Use this to select the best model for a task."
)
def list_models() -> ModelListing:
    """List available OpenAI models with detailed information."""
    # Get models from API for availability checking
    api_models = client.models.list()
    api_model_ids = {m.id for m in api_models.data}

    # Use structured model listing
    return get_structured_model_listing("openai", api_model_ids)


@mcp.tool(
    description="Checks OpenAI Tool server status and API connectivity. Returns version info, model availability, and a list of available functions."
)
def server_info() -> ServerInfo:
    """Get server status and OpenAI configuration."""
    # Test API key by listing models
    models = client.models.list()
    available_models = [
        m.id for m in models.data if m.id.startswith(("gpt", "dall-e", "text-", "o1"))
    ]

    # Add embedding capabilities to the server info
    info = build_server_info(
        provider_name="OpenAI",
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
