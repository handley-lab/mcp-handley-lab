"""Image Generation Tool via MCP.

Provides image generation using multiple providers (Gemini, OpenAI, Grok).
"""

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from mcp_handley_lab.common.pricing import calculate_cost
from mcp_handley_lab.llm.registry import get_adapter, resolve_model

mcp = FastMCP("Image Tool")


@mcp.tool(
    description="Generate an image from a text prompt. "
    "Supports Gemini (imagen-*), OpenAI (dall-e-*), and Grok (grok-*-image) models. "
    "Returns: {file_path, file_size_bytes, model, provider, cost, enhanced_prompt?, original_prompt}."
)
def generate(
    prompt: str = Field(
        ...,
        description="Text description of the image to generate.",
    ),
    output_file: str = Field(
        ...,
        description="File path to save the generated image (PNG format).",
    ),
    model: str = Field(
        default="imagen-4.0-generate-001",
        description="Image model. Provider auto-detected from name.",
    ),
    size: str = Field(
        default="",
        description="Image size (e.g., '1024x1024'). Provider-specific.",
    ),
    quality: str = Field(
        default="",
        description="Image quality (e.g., 'hd'). Provider-specific.",
    ),
    aspect_ratio: str = Field(
        default="",
        description="Aspect ratio (e.g., '16:9'). Provider-specific.",
    ),
) -> dict[str, Any]:
    """Generate an image from a text prompt."""
    if not prompt.strip():
        raise ValueError("Prompt is required and cannot be empty")

    provider, canonical_model, _ = resolve_model(model)

    # Get the image generation adapter
    try:
        generation_func = get_adapter(provider, "image_generation")
    except ValueError as e:
        raise ValueError(
            f"Image generation not supported for {provider} models. "
            f"Supported: Gemini (imagen-*), OpenAI (dall-e-*), Grok (grok-*-image)"
        ) from e

    # Build kwargs for provider-specific options
    kwargs = {}
    if size:
        kwargs["size"] = size
    if quality:
        kwargs["quality"] = quality
    if aspect_ratio:
        kwargs["aspect_ratio"] = aspect_ratio

    # Generate the image
    response_data = generation_func(prompt=prompt, model=canonical_model, **kwargs)
    image_bytes = response_data["image_bytes"]
    input_tokens = response_data.get("input_tokens", 0)
    output_tokens = response_data.get("output_tokens", 1)

    # Save to specified file
    filepath = Path(output_file)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_bytes(image_bytes)

    cost = calculate_cost(
        canonical_model, input_tokens, output_tokens, provider, images_generated=1
    )

    return {
        "file_path": str(filepath),
        "file_size_bytes": len(image_bytes),
        "model": canonical_model,
        "provider": provider,
        "cost": cost,
        "enhanced_prompt": response_data.get("enhanced_prompt", ""),
        "original_prompt": prompt,
    }
