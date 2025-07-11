#!/usr/bin/env python3
"""
Test script to examine image generation outputs from all providers.
This will help us understand what metadata is available for extraction.
"""
from pathlib import Path

from mcp_handley_lab.llm.gemini.tool import generate_image as gemini_generate_image
from mcp_handley_lab.llm.openai.tool import generate_image as openai_generate_image


def test_openai_image_generation():
    """Test OpenAI DALL-E image generation and examine output structure."""
    print("🎨 Testing OpenAI Image Generation")
    print("=" * 50)

    try:
        result = openai_generate_image(
            prompt="A simple red circle on white background",
            model="dall-e-3",
            size="1024x1024",
            quality="standard",
            agent_name="image_test",
        )

        print(f"Result type: {type(result)}")
        print(f"Result attributes: {dir(result)}")

        if hasattr(result, "__dict__"):
            print(f"Result dict: {result.__dict__}")

        # Check if it's a file path
        if isinstance(result, str):
            print(f"Generated image path: {result}")
            if Path(result).exists():
                print("File exists: True")
                print(f"File size: {Path(result).stat().st_size} bytes")
            else:
                print("File exists: False")

    except Exception as e:
        print(f"❌ OpenAI image generation failed: {e}")
        import traceback

        traceback.print_exc()

    print("\n")


def test_gemini_image_generation():
    """Test Gemini Imagen image generation and examine output structure."""
    print("🎨 Testing Gemini Image Generation")
    print("=" * 50)

    try:
        result = gemini_generate_image(
            prompt="A simple blue square on white background",
            model="imagen-3",
            agent_name="image_test",
        )

        print(f"Result type: {type(result)}")
        print(f"Result attributes: {dir(result)}")

        if hasattr(result, "__dict__"):
            print(f"Result dict: {result.__dict__}")

        # Check if it's a file path
        if isinstance(result, str):
            print(f"Generated image path: {result}")
            if Path(result).exists():
                print("File exists: True")
                print(f"File size: {Path(result).stat().st_size} bytes")
            else:
                print("File exists: False")

    except Exception as e:
        print(f"❌ Gemini image generation failed: {e}")
        import traceback

        traceback.print_exc()

    print("\n")


def test_image_generation_with_different_params():
    """Test image generation with various parameters to see what affects output."""
    print("🔍 Testing Image Generation Parameter Variations")
    print("=" * 60)

    # Test OpenAI with different parameters
    try:
        print("Testing OpenAI DALL-E 2...")
        result_dalle2 = openai_generate_image(
            prompt="A cat wearing a hat",
            model="dall-e-2",
            size="512x512",
            agent_name="param_test",
        )
        print(f"DALL-E 2 result: {type(result_dalle2)}")

        print("Testing OpenAI DALL-E 3 HD...")
        result_dalle3_hd = openai_generate_image(
            prompt="A cat wearing a hat",
            model="dall-e-3",
            size="1024x1024",
            quality="hd",
            agent_name="param_test",
        )
        print(f"DALL-E 3 HD result: {type(result_dalle3_hd)}")

    except Exception as e:
        print(f"❌ OpenAI parameter test failed: {e}")

    # Test Gemini with different models
    try:
        print("Testing Gemini Imagen 4...")
        result_img4 = gemini_generate_image(
            prompt="A dog in a park", model="imagen-4", agent_name="param_test"
        )
        print(f"Imagen 4 result: {type(result_img4)}")

        print("Testing Gemini Imagen 4 Ultra...")
        result_img4_ultra = gemini_generate_image(
            prompt="A dog in a park", model="imagen-4-ultra", agent_name="param_test"
        )
        print(f"Imagen 4 Ultra result: {type(result_img4_ultra)}")

    except Exception as e:
        print(f"❌ Gemini parameter test failed: {e}")

    print("\n")


def examine_raw_api_responses():
    """Examine the raw API responses to understand available metadata."""
    print("🔬 Examining Raw API Response Structures")
    print("=" * 50)

    # This would require modifying the actual tool functions to return raw responses
    # For now, let's examine what we can from the current implementations

    print("To examine raw API responses, we need to:")
    print("1. Look at the current implementation code")
    print("2. Identify what metadata is available but not captured")
    print("3. Design structured output models for image generation")

    print("\n")


def main():
    """Run comprehensive image generation output examination."""
    print("🚀 Starting Image Generation Output Analysis")
    print("=" * 60)
    print()

    test_openai_image_generation()
    test_gemini_image_generation()
    test_image_generation_with_different_params()
    examine_raw_api_responses()

    print("✅ Image generation analysis completed!")
    print("\nNext steps:")
    print("- Examine current implementation code to see raw API responses")
    print("- Design structured output models for image generation metadata")
    print("- Implement metadata extraction in image generation tools")


if __name__ == "__main__":
    main()
