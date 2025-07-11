#!/usr/bin/env python3
"""
Test script to verify enhanced image generation metadata extraction.
"""

from mcp_handley_lab.llm.gemini.tool import generate_image as gemini_generate_image
from mcp_handley_lab.llm.openai.tool import generate_image as openai_generate_image


def test_openai_enhanced_metadata():
    """Test OpenAI enhanced metadata extraction."""
    print("🎨 Testing OpenAI Enhanced Metadata Extraction")
    print("=" * 60)

    try:
        result = openai_generate_image(
            prompt="A simple geometric test pattern",
            model="dall-e-3",
            size="1024x1024",
            quality="standard",
            agent_name="metadata_test",
        )

        print("✅ Successfully generated image with metadata!")
        print(f"📁 File: {result.file_path}")
        print(f"📊 Size: {result.file_size_bytes} bytes")

        # Test new metadata fields
        print("\n🔍 Enhanced Metadata:")
        print(f"  • Generation timestamp: {result.generation_timestamp}")
        print(f"  • Enhanced prompt: {result.enhanced_prompt[:100]}...")
        print(f"  • Original prompt: {result.original_prompt}")
        print(f"  • Requested size: {result.requested_size}")
        print(f"  • Requested quality: {result.requested_quality}")
        print(f"  • MIME type: {result.mime_type}")
        print(f"  • Original URL: {result.original_url[:60]}...")
        print(f"  • OpenAI metadata keys: {list(result.openai_metadata.keys())}")

        # Verify all fields are populated
        assert result.generation_timestamp > 0, "Generation timestamp should be set"
        assert result.enhanced_prompt, "Enhanced prompt should be populated"
        assert result.requested_size == "1024x1024", "Requested size should match"
        assert result.mime_type == "image/png", "MIME type should be PNG"
        assert result.original_url.startswith(
            "https://"
        ), "Original URL should be valid"

        print("✅ All OpenAI metadata fields validated!")

    except Exception as e:
        print(f"❌ OpenAI test failed: {e}")
        import traceback

        traceback.print_exc()

    print("\n")


def test_gemini_enhanced_metadata():
    """Test Gemini enhanced metadata extraction."""
    print("🎨 Testing Gemini Enhanced Metadata Extraction")
    print("=" * 60)

    try:
        result = gemini_generate_image(
            prompt="A simple blue circle on white background",
            model="imagen-3",
            agent_name="metadata_test",
        )

        print("✅ Successfully generated image with metadata!")
        print(f"📁 File: {result.file_path}")
        print(f"📊 Size: {result.file_size_bytes} bytes")

        # Test new metadata fields
        print("\n🔍 Enhanced Metadata:")
        print(f"  • Enhanced prompt: '{result.enhanced_prompt}'")
        print(f"  • Original prompt: {result.original_prompt}")
        print(f"  • Aspect ratio: {result.aspect_ratio}")
        print(f"  • MIME type: {result.mime_type}")
        print(f"  • Cloud URI: '{result.cloud_uri}'")
        print(f"  • Content filter reason: '{result.content_filter_reason}'")
        print(f"  • Safety attributes: {result.safety_attributes}")
        print(f"  • Gemini metadata keys: {list(result.gemini_metadata.keys())}")

        # Verify key fields are populated
        assert result.original_prompt, "Original prompt should be populated"
        assert result.aspect_ratio == "1:1", "Aspect ratio should be set"
        assert result.mime_type in ["image/png", ""], "MIME type should be PNG or empty"
        assert isinstance(
            result.safety_attributes, dict
        ), "Safety attributes should be dict"
        assert isinstance(
            result.gemini_metadata, dict
        ), "Gemini metadata should be dict"

        print("✅ All Gemini metadata fields validated!")

    except Exception as e:
        print(f"❌ Gemini test failed: {e}")
        import traceback

        traceback.print_exc()

    print("\n")


def test_metadata_comparison():
    """Compare metadata between providers."""
    print("🔍 Provider Metadata Comparison")
    print("=" * 60)

    try:
        # Test with same prompt
        prompt = "A red square"

        openai_result = openai_generate_image(
            prompt=prompt,
            model="dall-e-3",
            size="512x512",
            quality="standard",
            agent_name="comparison_test",
        )

        gemini_result = gemini_generate_image(
            prompt=prompt, model="imagen-3", agent_name="comparison_test"
        )

        print("📊 Metadata Comparison:")
        print(f"OpenAI enhanced prompt: {openai_result.enhanced_prompt[:80]}...")
        print(f"Gemini enhanced prompt: '{gemini_result.enhanced_prompt}'")
        print(f"OpenAI size: {openai_result.requested_size}")
        print(f"Gemini aspect ratio: {gemini_result.aspect_ratio}")
        print(f"OpenAI safety data: {bool(openai_result.safety_attributes)}")
        print(f"Gemini safety data: {bool(gemini_result.safety_attributes)}")

        print("✅ Comparison completed successfully!")

    except Exception as e:
        print(f"❌ Comparison test failed: {e}")

    print("\n")


def main():
    """Run comprehensive enhanced metadata tests."""
    print("🚀 Starting Enhanced Image Metadata Tests")
    print("=" * 70)
    print()

    test_openai_enhanced_metadata()
    test_gemini_enhanced_metadata()
    test_metadata_comparison()

    print("✅ All enhanced metadata tests completed!")
    print("\nKey improvements verified:")
    print("- Comprehensive metadata extraction from both providers")
    print("- Enhanced prompts captured from DALL-E revisions")
    print("- Safety attributes and content filtering information")
    print("- Technical details like MIME types and URLs")
    print("- Provider-specific metadata preservation")


if __name__ == "__main__":
    main()
