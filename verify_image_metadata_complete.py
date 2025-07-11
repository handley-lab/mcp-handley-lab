#!/usr/bin/env python3
"""
Final verification script showing all image generation metadata being captured.
"""
import json

from mcp_handley_lab.llm.gemini.tool import generate_image as gemini_generate_image
from mcp_handley_lab.llm.openai.tool import generate_image as openai_generate_image


def demonstrate_metadata_extraction():
    """Demonstrate comprehensive metadata extraction from both providers."""
    print("🎨 Comprehensive Image Generation Metadata Demonstration")
    print("=" * 70)

    # Test OpenAI DALL-E 3
    print("\n🤖 OpenAI DALL-E 3 Metadata:")
    try:
        openai_result = openai_generate_image(
            prompt="A futuristic cityscape at sunset",
            model="dall-e-3",
            size="1024x1024",
            quality="hd",
            agent_name="demo",
        )

        metadata = {
            "Core Fields": {
                "message": openai_result.message,
                "file_path": openai_result.file_path,
                "file_size_bytes": openai_result.file_size_bytes,
                "agent_name": openai_result.agent_name,
            },
            "Usage Statistics": {
                "input_tokens": openai_result.usage.input_tokens,
                "output_tokens": openai_result.usage.output_tokens,
                "cost": openai_result.usage.cost,
                "model_used": openai_result.usage.model_used,
            },
            "Generation Metadata": {
                "generation_timestamp": openai_result.generation_timestamp,
                "enhanced_prompt": openai_result.enhanced_prompt[:100] + "..."
                if openai_result.enhanced_prompt
                else "",
                "original_prompt": openai_result.original_prompt,
            },
            "Request Parameters": {
                "requested_size": openai_result.requested_size,
                "requested_quality": openai_result.requested_quality,
                "requested_format": openai_result.requested_format,
                "aspect_ratio": openai_result.aspect_ratio,
            },
            "Safety & Filtering": {
                "safety_attributes": openai_result.safety_attributes,
                "content_filter_reason": openai_result.content_filter_reason,
            },
            "Technical Details": {
                "mime_type": openai_result.mime_type,
                "cloud_uri": openai_result.cloud_uri,
                "original_url": openai_result.original_url[:50] + "..."
                if openai_result.original_url
                else "",
            },
            "Provider-Specific": {
                "openai_metadata": openai_result.openai_metadata,
            },
        }

        print(json.dumps(metadata, indent=2))

    except Exception as e:
        print(f"❌ OpenAI failed: {e}")

    # Test Gemini Imagen
    print("\n🧠 Gemini Imagen Metadata:")
    try:
        gemini_result = gemini_generate_image(
            prompt="A serene mountain landscape with a lake",
            model="imagen-3",
            agent_name="demo",
        )

        metadata = {
            "Core Fields": {
                "message": gemini_result.message,
                "file_path": gemini_result.file_path,
                "file_size_bytes": gemini_result.file_size_bytes,
                "agent_name": gemini_result.agent_name,
            },
            "Usage Statistics": {
                "input_tokens": gemini_result.usage.input_tokens,
                "output_tokens": gemini_result.usage.output_tokens,
                "cost": gemini_result.usage.cost,
                "model_used": gemini_result.usage.model_used,
            },
            "Generation Metadata": {
                "generation_timestamp": gemini_result.generation_timestamp,
                "enhanced_prompt": gemini_result.enhanced_prompt,
                "original_prompt": gemini_result.original_prompt,
            },
            "Request Parameters": {
                "requested_size": gemini_result.requested_size,
                "requested_quality": gemini_result.requested_quality,
                "requested_format": gemini_result.requested_format,
                "aspect_ratio": gemini_result.aspect_ratio,
            },
            "Safety & Filtering": {
                "safety_attributes": gemini_result.safety_attributes,
                "content_filter_reason": gemini_result.content_filter_reason,
            },
            "Technical Details": {
                "mime_type": gemini_result.mime_type,
                "cloud_uri": gemini_result.cloud_uri,
                "original_url": gemini_result.original_url,
            },
            "Provider-Specific": {
                "gemini_metadata": gemini_result.gemini_metadata,
            },
        }

        print(json.dumps(metadata, indent=2))

    except Exception as e:
        print(f"❌ Gemini failed: {e}")

    print("\n✅ Comprehensive metadata extraction demonstration complete!")
    print("\n📋 Summary of Enhanced Metadata Captured:")
    print("• Generation timestamps for tracking when images were created")
    print("• Enhanced prompts showing AI improvements to user prompts")
    print("• Original prompts preserving user input")
    print("• Request parameters (size, quality, format, aspect ratio)")
    print("• Safety attributes and content filtering information")
    print("• Technical details (MIME types, URLs, cloud storage)")
    print("• Provider-specific metadata for advanced features")
    print("• Complete usage statistics including costs")


if __name__ == "__main__":
    demonstrate_metadata_extraction()
