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
    "Supports Gemini (imagen-*, gemini-*-image), OpenAI (dall-e-*), and Grok (grok-*-image) models. "
    "Nano Banana models (gemini-*-image) support input_images for editing/reference. "
    "Returns: {file_path, file_size_bytes, model, provider, cost, enhanced_prompt?, original_prompt}."
)
def generate(
    prompt: str = Field(
        ...,
        description="Text description of the image to generate.",
    ),
    output_file: str = Field(
        ...,
        description="File path to save the generated image. Nano Banana outputs JPEG, Imagen outputs PNG.",
    ),
    model: str = Field(
        default="gemini-3-pro-image-preview",
        description="Image model. Provider auto-detected from name.",
    ),
    input_images: list[str] = Field(
        default=[],
        description="Input images for editing (Nano Banana models only). "
        "Provide images to edit/transform based on the prompt. "
        "Accepts: local paths, URLs, or data URIs.",
    ),
    size: str = Field(
        default="",
        description="Image size. For Nano Banana: '1K', '2K', '4K'. For others: '1024x1024'.",
    ),
    quality: str = Field(
        default="",
        description="Image quality (e.g., 'hd'). Provider-specific.",
    ),
    aspect_ratio: str = Field(
        default="",
        description="Aspect ratio. Nano Banana supports: 1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9.",
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
    if input_images:
        kwargs["input_images"] = input_images

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
