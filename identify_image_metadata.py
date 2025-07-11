#!/usr/bin/env python3
"""
Script to identify specific metadata fields available from image generation APIs
that we should capture in our structured outputs.
"""
import os

import google.genai as genai
import openai
from google.genai.types import GenerateImagesConfig


def analyze_openai_metadata():
    """Analyze OpenAI DALL-E response metadata we can capture."""
    print("📊 OpenAI DALL-E Metadata Analysis")
    print("=" * 50)

    try:
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        response = client.images.generate(
            model="dall-e-3",
            prompt="A simple test image",
            size="1024x1024",
            quality="standard",
            n=1,
        )

        print("✅ Available metadata fields:")
        print(f"  • created: {response.created} (timestamp)")
        print(f"  • background: {response.background} (possibly null)")
        print(f"  • output_format: {response.output_format} (possibly null)")
        print(f"  • quality: {response.quality} (possibly null)")
        print(f"  • size: {response.size} (possibly null)")
        print(f"  • usage: {response.usage} (possibly null)")

        # Image-specific metadata
        image = response.data[0]
        print("\n✅ Per-image metadata:")
        print(f"  • url: {image.url[:60]}... (image URL)")
        print(f"  • revised_prompt: {image.revised_prompt[:60]}... (enhanced prompt)")
        print(f"  • b64_json: {image.b64_json} (base64 if requested)")

        print("\n📋 Currently captured:")
        print("  • image_bytes (downloaded from URL)")
        print("  • input_tokens (estimated)")
        print("  • output_tokens (fixed to 1)")

        print("\n🔍 Missing metadata we should capture:")
        print("  • created (generation timestamp)")
        print("  • revised_prompt (DALL-E's enhanced prompt)")
        print("  • original_url (before download)")
        print("  • requested_size (from parameters)")
        print("  • requested_quality (from parameters)")
        print("  • model_version (from response)")

    except Exception as e:
        print(f"❌ Analysis failed: {e}")

    print("\n")


def analyze_gemini_metadata():
    """Analyze Gemini Imagen response metadata we can capture."""
    print("📊 Gemini Imagen Metadata Analysis")
    print("=" * 50)

    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

        response = client.models.generate_images(
            model="imagen-3.0-generate-002",
            prompt="A simple test image",
            config=GenerateImagesConfig(number_of_images=1, aspect_ratio="1:1"),
        )

        print("✅ Available response metadata:")
        print(
            f"  • positive_prompt_safety_attributes: {response.positive_prompt_safety_attributes}"
        )

        # Generated image metadata
        image = response.generated_images[0]
        print("\n✅ Per-image metadata:")
        print(f"  • enhanced_prompt: {image.enhanced_prompt} (enhanced prompt)")
        print(
            f"  • rai_filtered_reason: {image.rai_filtered_reason} (content filter reason)"
        )
        print(f"  • safety_attributes: {image.safety_attributes} (safety scores)")

        # Image object metadata
        img_obj = image.image
        print("\n✅ Image object metadata:")
        print(f"  • mime_type: {img_obj.mime_type} (content type)")
        print(f"  • gcs_uri: {img_obj.gcs_uri} (cloud storage URI)")
        print(f"  • image_bytes: {len(img_obj.image_bytes)} bytes")

        print("\n📋 Currently captured:")
        print("  • image_bytes")
        print("  • input_tokens (estimated)")

        print("\n🔍 Missing metadata we should capture:")
        print("  • enhanced_prompt (Gemini's enhanced prompt)")
        print("  • safety_attributes (safety scores)")
        print("  • rai_filtered_reason (content filter reason)")
        print("  • mime_type (image format)")
        print("  • gcs_uri (cloud storage URI if available)")
        print("  • positive_prompt_safety_attributes (prompt safety)")
        print("  • generation_model_version (actual model used)")

    except Exception as e:
        print(f"❌ Analysis failed: {e}")

    print("\n")


def design_enhanced_structure():
    """Design the enhanced ImageGenerationResult structure."""
    print("🏗️  Enhanced ImageGenerationResult Structure Design")
    print("=" * 60)

    print(
        """
class ImageGenerationResult(BaseModel):
    # Existing fields
    message: str
    file_path: str
    file_size_bytes: int
    usage: UsageStats
    agent_name: str = ""

    # New metadata fields (provider-agnostic)
    generation_timestamp: int = 0  # Unix timestamp
    enhanced_prompt: str = ""  # AI-enhanced version of original prompt
    original_prompt: str = ""  # Original user prompt

    # Request parameters (what was requested)
    requested_size: str = ""  # e.g., "1024x1024"
    requested_quality: str = ""  # e.g., "standard", "hd"
    requested_format: str = ""  # e.g., "png", "jpg"
    aspect_ratio: str = ""  # e.g., "1:1", "16:9"

    # Safety and content filtering
    safety_attributes: dict[str, Any] = {}  # Safety scores/flags
    content_filter_reason: str = ""  # If content was filtered

    # Provider-specific metadata
    openai_metadata: dict[str, Any] = {}  # OpenAI-specific fields
    gemini_metadata: dict[str, Any] = {}  # Gemini-specific fields

    # Technical details
    mime_type: str = ""  # e.g., "image/png"
    cloud_uri: str = ""  # Cloud storage URI if available
    original_url: str = ""  # Original download URL (OpenAI)
    """
    )

    print("\n📝 Implementation Strategy:")
    print("1. Extend ImageGenerationResult with new fields")
    print("2. Update adapter functions to extract all available metadata")
    print("3. Add provider-specific metadata extraction")
    print("4. Preserve backward compatibility with existing structure")
    print("5. Add comprehensive VCR tests for all metadata fields")


def main():
    """Run comprehensive metadata analysis."""
    print("🚀 Starting Image Generation Metadata Analysis")
    print("=" * 70)
    print()

    analyze_openai_metadata()
    analyze_gemini_metadata()
    design_enhanced_structure()

    print("✅ Metadata analysis completed!")
    print("\nNext steps:")
    print("1. Update shared/models.py with enhanced ImageGenerationResult")
    print("2. Modify OpenAI and Gemini adapters to extract metadata")
    print("3. Update shared.py image processing to handle new fields")
    print("4. Add comprehensive tests for metadata extraction")


if __name__ == "__main__":
    main()
